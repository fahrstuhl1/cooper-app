"""Sendet HA-Benachrichtigungen über den Supervisor-REST-API.

Läuft als Daemon-Thread, prüft täglich um notify_hour Uhr auf:
- Überfällige / bald fällige Gesundheitstermine
- Futter-Vorräte mit niedrigem Stand
"""
import datetime
import json
import logging
import os
import threading
import time
import urllib.request
from zoneinfo import ZoneInfo

import db

log = logging.getLogger("cooper.notify")

SUPERVISOR_TOKEN = os.environ.get("SUPERVISOR_TOKEN", "")
_HA_BASE = "http://supervisor/core/api"


def _ha_post(path, payload):
    if not SUPERVISOR_TOKEN:
        log.debug("Kein SUPERVISOR_TOKEN – Benachrichtigung übersprungen")
        return False
    url = _HA_BASE + path
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Authorization": f"Bearer {SUPERVISOR_TOKEN}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            log.info("HA-API %s → HTTP %s", path, resp.status)
            return True
    except Exception as exc:
        log.warning("HA-API Fehler (%s): %s", path, exc)
        return False


def send_notification(service, title, message):
    """Feuert eine Notification über den angegebenen notify-Dienst."""
    return _ha_post(f"/services/notify/{service}", {"title": title, "message": message})


def _build_message(health_reminder_days, local_tz=None):
    if local_tz is None:
        local_tz = ZoneInfo("Europe/Berlin")
    today = datetime.datetime.now(local_tz).date()
    horizon = (today + datetime.timedelta(days=health_reminder_days)).isoformat()

    animals = {a["id"]: a["name"] for a in db.list_animals()}
    lines = []

    upcoming = db.upcoming_health(today.isoformat(), horizon)
    overdue = [e for e in upcoming if e.get("due_date", "") < today.isoformat()]
    due_soon = [e for e in upcoming if e.get("due_date", "") >= today.isoformat()]

    for e in overdue[:4]:
        animal = animals.get(e.get("animal_id"), "")
        prefix = f"{animal}: " if animal else ""
        lines.append(f"⚠️ {prefix}{e['title']} – überfällig seit {e['due_date']}")

    for e in due_soon[:4]:
        animal = animals.get(e.get("animal_id"), "")
        prefix = f"{animal}: " if animal else ""
        lines.append(f"📅 {prefix}{e['title']} – fällig {e['due_date']}")

    low = db.low_stock_products()
    for p in low[:4]:
        animal = animals.get(p.get("animal_id"), "")
        prefix = f"{animal}: " if animal else ""
        daily = p["daily_portion_g"] or 1
        days = round(p["stock_g"] / daily, 1)
        lines.append(f"📦 {prefix}{p['name']} – noch {days} Tage Vorrat")

    return "\n".join(lines)


def send_test_notification(config):
    """Sendet immer eine Test-Benachrichtigung, auch wenn keine Erinnerungen vorliegen."""
    local_tz = ZoneInfo(config.get("timezone", "Europe/Berlin"))
    msg = _build_message(config.get("health_reminder_days", 30), local_tz)
    if not msg:
        msg = "Keine offenen Erinnerungen – alles im Grünen ✅"
    service = config.get("notification_service", "notify")
    return send_notification(service, "🐾 Cooper – Test", msg)


def check_and_notify(config):
    """Einmalige Prüfung und Benachrichtigung – kann auch von außen aufgerufen werden."""
    local_tz = ZoneInfo(config.get("timezone", "Europe/Berlin"))
    msg = _build_message(config.get("health_reminder_days", 30), local_tz)
    if not msg:
        log.debug("Keine Erinnerungen zu senden")
        return False
    service = config.get("notification_service", "notify")
    return send_notification(service, "🐾 Cooper – Erinnerungen", msg)


def start_scheduler(config):
    """Startet den Hintergrund-Thread für tägliche Benachrichtigungen."""
    notify_hour = int(config.get("notify_hour", 8))
    local_tz = ZoneInfo(config.get("timezone", "Europe/Berlin"))

    def loop():
        last_sent_date = None
        while True:
            now = datetime.datetime.now(local_tz)
            today = now.date()
            if now.hour >= notify_hour and last_sent_date != today:
                try:
                    check_and_notify(config)
                except Exception as exc:
                    log.warning("Fehler beim Benachrichtigen: %s", exc)
                last_sent_date = today
            next_hour = (now + datetime.timedelta(hours=1)).replace(minute=2, second=0, microsecond=0)
            time.sleep(max((next_hour - now).total_seconds(), 60))

    t = threading.Thread(target=loop, daemon=True, name="cooper-notifier")
    t.start()
    log.info("Benachrichtigungs-Scheduler gestartet (täglich um %02d:00 Uhr)", notify_hour)

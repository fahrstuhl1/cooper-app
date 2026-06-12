"""Flask-Routen für Cooper."""
import calendar
import datetime
import logging
from zoneinfo import ZoneInfo

from flask import Flask, jsonify, request, send_from_directory

import db

LOCAL_TZ = ZoneInfo("Europe/Berlin")
UTC = datetime.timezone.utc

log = logging.getLogger("cooper")


def create_app(config):
    app = Flask(__name__, static_folder=None)
    persons = config["persons"]

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def resolve_person():
        """Ermittelt die aktive Person: Ingress-Header gewinnt über Toggle."""
        header_name = (
            request.headers.get("X-Remote-User-Display-Name")
            or request.headers.get("X-Remote-User-Name")
        )
        if header_name:
            for p in persons:
                if p.lower() == header_name.strip().lower():
                    return p

        body = request.get_json(silent=True) or {}
        candidate = body.get("person") or request.args.get("person")
        if candidate in persons:
            return candidate

        return None

    def parse_ts(value):
        """Parst einen ISO-Zeitstempel (mit oder ohne Z) zu UTC-ISO-String."""
        if not value:
            return db.utcnow_iso()
        text = value.strip()
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            dt = datetime.datetime.fromisoformat(text)
        except ValueError:
            return db.utcnow_iso()
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=LOCAL_TZ)
        dt_utc = dt.astimezone(UTC)
        return dt_utc.strftime("%Y-%m-%dT%H:%M:%SZ")

    def local_day_bounds_utc(now_utc=None):
        now_utc = now_utc or datetime.datetime.now(UTC)
        now_local = now_utc.astimezone(LOCAL_TZ)
        start_local = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
        end_local = start_local + datetime.timedelta(days=1)
        start_utc = start_local.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        end_utc = end_local.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        return start_utc, end_utc

    def minutes_since(ts_utc, now_utc=None):
        if not ts_utc:
            return None
        now_utc = now_utc or datetime.datetime.now(UTC)
        dt = datetime.datetime.strptime(ts_utc, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
        delta = now_utc - dt
        return max(0, int(delta.total_seconds() // 60))

    def add_months(d, months):
        month_index = d.month - 1 + months
        year = d.year + month_index // 12
        month = month_index % 12 + 1
        day = min(d.day, calendar.monthrange(year, month)[1])
        return datetime.date(year, month, day)

    def age_string(birthdate_str, today):
        try:
            birthdate = datetime.date.fromisoformat(birthdate_str)
        except ValueError:
            return ""
        if birthdate > today:
            return ""
        total_months = (today.year - birthdate.year) * 12 + (today.month - birthdate.month)
        anniversary = add_months(birthdate, total_months)
        if anniversary > today:
            total_months -= 1
            anniversary = add_months(birthdate, total_months)
        weeks = (today - anniversary).days // 7

        parts = []
        if total_months > 0:
            parts.append(f"{total_months} Monat" + ("e" if total_months != 1 else ""))
        if weeks > 0 or total_months == 0:
            parts.append(f"{weeks} Woche" + ("n" if weeks != 1 else ""))
        return ", ".join(parts)

    def age_weeks(birthdate_str, on_date):
        try:
            birthdate = datetime.date.fromisoformat(birthdate_str)
        except ValueError:
            return None
        if on_date < birthdate:
            return 0
        return (on_date - birthdate).days // 7

    def next_due_date(due_date, repeat_weeks):
        if not due_date or not repeat_weeks:
            return due_date
        today = datetime.datetime.now(LOCAL_TZ).date()
        due = datetime.date.fromisoformat(due_date)
        while due < today:
            due = due + datetime.timedelta(weeks=int(repeat_weeks))
        return due.isoformat()

    # ------------------------------------------------------------------
    # Static frontend
    # ------------------------------------------------------------------

    @app.get("/")
    def index():
        return send_from_directory("web", "index.html")

    @app.get("/api/meta")
    def meta():
        today = datetime.datetime.now(LOCAL_TZ).date()
        return jsonify(
            {
                "dog_name": config["dog_name"],
                "birthdate": config["birthdate"],
                "persons": persons,
                "daily_food_target_g": config["daily_food_target_g"],
                "health_reminder_days": config["health_reminder_days"],
                "age": age_string(config["birthdate"], today),
            }
        )

    # ------------------------------------------------------------------
    # Dashboard
    # ------------------------------------------------------------------

    @app.get("/api/dashboard")
    def dashboard():
        now_utc = datetime.datetime.now(UTC)
        today = now_utc.astimezone(LOCAL_TZ).date()
        day_start, day_end = local_day_bounds_utc(now_utc)

        last_walk = db.last_walk_of_kind()
        last_pee = db.last_walk_of_kind("pee")
        last_poop = db.last_walk_of_kind("poop")

        walks_today = db.count_walks_today(day_start, day_end)
        food_today = db.food_total_today(day_start, day_end)

        horizon = (today + datetime.timedelta(days=config["health_reminder_days"])).isoformat()
        upcoming = db.upcoming_health(today.isoformat(), horizon)
        for item in upcoming:
            item["due_date"] = next_due_date(item["due_date"], item["repeat_weeks"])
            item["overdue"] = item["due_date"] < today.isoformat()

        weights = db.list_weights()
        weight_history = [
            {"date": w["date"], "weight_kg": w["weight_kg"]} for w in weights[-20:]
        ]
        latest = db.latest_weight()

        commands = db.list_commands()
        commands_done = sum(1 for c in commands if c["status"] == "sitzt")

        return jsonify(
            {
                "dog_name": config["dog_name"],
                "age": age_string(config["birthdate"], today),
                "persons": persons,
                "walks": {
                    "minutes_since_last": minutes_since(last_walk["ts_utc"], now_utc) if last_walk else None,
                    "minutes_since_pee": minutes_since(last_pee["ts_utc"], now_utc) if last_pee else None,
                    "minutes_since_poop": minutes_since(last_poop["ts_utc"], now_utc) if last_poop else None,
                    "today_count": walks_today,
                },
                "feeding": {
                    "today_g": food_today,
                    "target_g": config["daily_food_target_g"],
                },
                "upcoming_health": upcoming,
                "weight": {
                    "latest": latest,
                    "history": weight_history,
                },
                "commands": {
                    "done": commands_done,
                    "total": len(commands),
                },
            }
        )

    @app.get("/api/ha-sensors")
    def ha_sensors():
        now_utc = datetime.datetime.now(UTC)
        today = now_utc.astimezone(LOCAL_TZ).date()
        day_start, day_end = local_day_bounds_utc(now_utc)

        last_walk = db.last_walk_of_kind()
        last_pee = db.last_walk_of_kind("pee")
        food_today = db.food_total_today(day_start, day_end)

        horizon = (today + datetime.timedelta(days=config["health_reminder_days"])).isoformat()
        upcoming = db.upcoming_health(today.isoformat(), horizon)
        next_due = None
        if upcoming:
            sorted_upcoming = sorted(
                upcoming, key=lambda e: next_due_date(e["due_date"], e["repeat_weeks"]) or "9999"
            )
            first = sorted_upcoming[0]
            next_due = {
                "title": first["title"],
                "type": first["type"],
                "due_date": next_due_date(first["due_date"], first["repeat_weeks"]),
            }

        return jsonify(
            {
                "minutes_since_last_walk": minutes_since(last_walk["ts_utc"], now_utc) if last_walk else None,
                "minutes_since_last_pee": minutes_since(last_pee["ts_utc"], now_utc) if last_pee else None,
                "fed_today_g": food_today,
                "next_due_health": next_due,
            }
        )

    # ------------------------------------------------------------------
    # Walks
    # ------------------------------------------------------------------

    @app.get("/api/walks")
    def get_walks():
        limit = request.args.get("limit", type=int)
        return jsonify(db.list_walks(limit=limit))

    @app.post("/api/walks")
    def post_walk():
        body = request.get_json(silent=True) or {}
        person = resolve_person()
        if not person:
            return jsonify({"error": "Unbekannte oder fehlende Person"}), 400

        ts_utc = parse_ts(body.get("ts_utc"))
        pee = bool(body.get("pee", False))
        poop = bool(body.get("poop", False))
        duration_min = body.get("duration_min")
        note = body.get("note") or None

        walk = db.create_walk(ts_utc, person, pee, poop, duration_min, note)
        return jsonify(walk), 201

    @app.patch("/api/walks/<int:walk_id>")
    def patch_walk(walk_id):
        if not db.get_walk(walk_id):
            return jsonify({"error": "Eintrag nicht gefunden"}), 404
        body = request.get_json(silent=True) or {}
        fields = {}
        if "ts_utc" in body:
            fields["ts_utc"] = parse_ts(body["ts_utc"])
        if "pee" in body:
            fields["pee"] = bool(body["pee"])
        if "poop" in body:
            fields["poop"] = bool(body["poop"])
        if "duration_min" in body:
            fields["duration_min"] = body["duration_min"]
        if "note" in body:
            fields["note"] = body["note"]
        if "person" in body:
            if body["person"] not in persons:
                return jsonify({"error": "Unbekannte Person"}), 400
            fields["person"] = body["person"]
        walk = db.update_walk(walk_id, **fields)
        return jsonify(walk)

    @app.delete("/api/walks/<int:walk_id>")
    def delete_walk(walk_id):
        if not db.get_walk(walk_id):
            return jsonify({"error": "Eintrag nicht gefunden"}), 404
        db.delete_walk(walk_id)
        return "", 204

    # ------------------------------------------------------------------
    # Feedings
    # ------------------------------------------------------------------

    @app.get("/api/feedings")
    def get_feedings():
        limit = request.args.get("limit", type=int)
        return jsonify(
            {
                "items": db.list_feedings(limit=limit),
                "suggestions": db.recent_food_types(),
            }
        )

    @app.post("/api/feedings")
    def post_feeding():
        body = request.get_json(silent=True) or {}
        person = resolve_person()
        if not person:
            return jsonify({"error": "Unbekannte oder fehlende Person"}), 400

        food_type = (body.get("food_type") or "").strip()
        amount_g = body.get("amount_g")
        if not food_type or amount_g is None:
            return jsonify({"error": "Futterart und Menge sind erforderlich"}), 400
        try:
            amount_g = int(amount_g)
        except (TypeError, ValueError):
            return jsonify({"error": "Menge muss eine Zahl sein"}), 400

        ts_utc = parse_ts(body.get("ts_utc"))
        feeding = db.create_feeding(ts_utc, person, food_type, amount_g)
        return jsonify(feeding), 201

    @app.delete("/api/feedings/<int:feeding_id>")
    def delete_feeding(feeding_id):
        if not db.get_feeding(feeding_id):
            return jsonify({"error": "Eintrag nicht gefunden"}), 404
        db.delete_feeding(feeding_id)
        return "", 204

    # ------------------------------------------------------------------
    # Weights
    # ------------------------------------------------------------------

    @app.get("/api/weights")
    def get_weights():
        today = datetime.datetime.now(LOCAL_TZ).date()
        items = db.list_weights()
        for item in items:
            try:
                d = datetime.date.fromisoformat(item["date"])
                item["age_weeks"] = age_weeks(config["birthdate"], d)
            except ValueError:
                item["age_weeks"] = None
        return jsonify(items)

    @app.post("/api/weights")
    def post_weight():
        body = request.get_json(silent=True) or {}
        person = resolve_person()

        date = body.get("date") or datetime.datetime.now(LOCAL_TZ).date().isoformat()
        weight_kg = body.get("weight_kg")
        if weight_kg is None:
            return jsonify({"error": "Gewicht ist erforderlich"}), 400
        try:
            weight_kg = round(float(weight_kg), 2)
        except (TypeError, ValueError):
            return jsonify({"error": "Gewicht muss eine Zahl sein"}), 400

        weight = db.create_weight(date, weight_kg, person)
        return jsonify(weight), 201

    @app.delete("/api/weights/<int:weight_id>")
    def delete_weight(weight_id):
        if not db.get_weight(weight_id):
            return jsonify({"error": "Eintrag nicht gefunden"}), 404
        db.delete_weight(weight_id)
        return "", 204

    # ------------------------------------------------------------------
    # Health events
    # ------------------------------------------------------------------

    VALID_HEALTH_TYPES = {"Impfung", "Wurmkur", "Parasitenschutz", "Tierarzt-Termin", "Sonstiges"}

    @app.get("/api/health")
    def get_health_events():
        event_type = request.args.get("type")
        items = db.list_health(event_type=event_type)
        today = datetime.datetime.now(LOCAL_TZ).date().isoformat()
        for item in items:
            item["due_date"] = next_due_date(item["due_date"], item["repeat_weeks"])
            item["overdue"] = bool(item["due_date"] and item["due_date"] < today)
        return jsonify(items)

    @app.post("/api/health")
    def post_health():
        body = request.get_json(silent=True) or {}
        person = resolve_person()

        event_type = body.get("type")
        title = (body.get("title") or "").strip()
        date = body.get("date") or datetime.datetime.now(LOCAL_TZ).date().isoformat()
        note = body.get("note") or None
        due_date = body.get("due_date") or None
        repeat_weeks = body.get("repeat_weeks") or None

        if event_type not in VALID_HEALTH_TYPES:
            return jsonify({"error": "Ungültiger Ereignistyp"}), 400
        if not title:
            return jsonify({"error": "Titel ist erforderlich"}), 400

        if repeat_weeks and not due_date:
            try:
                base = datetime.date.fromisoformat(date)
                due_date = (base + datetime.timedelta(weeks=int(repeat_weeks))).isoformat()
            except (ValueError, TypeError):
                due_date = None

        event = db.create_health(event_type, title, date, note, due_date, repeat_weeks, person)
        return jsonify(event), 201

    @app.patch("/api/health/<int:event_id>")
    def patch_health(event_id):
        if not db.get_health(event_id):
            return jsonify({"error": "Eintrag nicht gefunden"}), 404
        body = request.get_json(silent=True) or {}
        fields = {}
        if "type" in body:
            if body["type"] not in VALID_HEALTH_TYPES:
                return jsonify({"error": "Ungültiger Ereignistyp"}), 400
            fields["type"] = body["type"]
        for key in ("title", "date", "note", "due_date", "repeat_weeks"):
            if key in body:
                fields[key] = body[key]
        event = db.update_health(event_id, **fields)
        return jsonify(event)

    @app.delete("/api/health/<int:event_id>")
    def delete_health(event_id):
        if not db.get_health(event_id):
            return jsonify({"error": "Eintrag nicht gefunden"}), 404
        db.delete_health(event_id)
        return "", 204

    # ------------------------------------------------------------------
    # Commands
    # ------------------------------------------------------------------

    VALID_COMMAND_STATUSES = ["neu", "in Arbeit", "sitzt"]

    @app.get("/api/commands")
    def get_commands():
        return jsonify(db.list_commands())

    @app.post("/api/commands")
    def post_command():
        body = request.get_json(silent=True) or {}
        name = (body.get("name") or "").strip()
        if not name:
            return jsonify({"error": "Name ist erforderlich"}), 400
        command = db.create_command(name)
        return jsonify(command), 201

    @app.patch("/api/commands/<int:command_id>")
    def patch_command(command_id):
        if not db.get_command(command_id):
            return jsonify({"error": "Kommando nicht gefunden"}), 404
        body = request.get_json(silent=True) or {}
        status = body.get("status")
        if status is None:
            current = db.get_command(command_id)
            idx = VALID_COMMAND_STATUSES.index(current["status"])
            status = VALID_COMMAND_STATUSES[(idx + 1) % len(VALID_COMMAND_STATUSES)]
        if status not in VALID_COMMAND_STATUSES:
            return jsonify({"error": "Ungültiger Status"}), 400
        command = db.update_command_status(command_id, status)
        return jsonify(command)

    @app.delete("/api/commands/<int:command_id>")
    def delete_command(command_id):
        if not db.get_command(command_id):
            return jsonify({"error": "Kommando nicht gefunden"}), 404
        db.delete_command(command_id)
        return "", 204

    # ------------------------------------------------------------------
    # Training sessions
    # ------------------------------------------------------------------

    @app.get("/api/sessions")
    def get_sessions():
        limit = request.args.get("limit", type=int)
        return jsonify(db.list_sessions(limit=limit))

    @app.post("/api/sessions")
    def post_session():
        body = request.get_json(silent=True) or {}
        person = resolve_person()
        if not person:
            return jsonify({"error": "Unbekannte oder fehlende Person"}), 400

        date = body.get("date") or datetime.datetime.now(LOCAL_TZ).date().isoformat()
        duration_min = body.get("duration_min")
        note = body.get("note") or None
        commands = body.get("commands") or []
        if not isinstance(commands, list):
            return jsonify({"error": "commands muss eine Liste sein"}), 400

        session = db.create_session(date, person, duration_min, note, commands)
        return jsonify(session), 201

    return app

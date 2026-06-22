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

SPECIES_ICONS = {"dog": "🐕", "cat": "🐱", "rabbit": "🐇", "bird": "🐦", "reptile": "🦎", "other": "🐾"}


def create_app(config):
    app = Flask(__name__, static_folder=None)
    persons = config["persons"]

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def resolve_person():
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
        return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    def local_day_bounds_utc(now_utc=None):
        now_utc = now_utc or datetime.datetime.now(UTC)
        now_local = now_utc.astimezone(LOCAL_TZ)
        start_local = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
        end_local = start_local + datetime.timedelta(days=1)
        start_utc = start_local.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        end_utc = end_local.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        return start_utc, end_utc

    def add_months(d, months):
        month_index = d.month - 1 + months
        year = d.year + month_index // 12
        month = month_index % 12 + 1
        day = min(d.day, calendar.monthrange(year, month)[1])
        return datetime.date(year, month, day)

    def age_string(birthdate_str, today):
        if not birthdate_str:
            return ""
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

    def next_due_date(due_date, repeat_weeks):
        if not due_date or not repeat_weeks:
            return due_date
        today = datetime.datetime.now(LOCAL_TZ).date()
        due = datetime.date.fromisoformat(due_date)
        while due < today:
            due = due + datetime.timedelta(weeks=int(repeat_weeks))
        return due.isoformat()

    def enrich_animal(animal):
        today = datetime.datetime.now(LOCAL_TZ).date()
        animal["icon"] = SPECIES_ICONS.get(animal.get("species", "other"), "🐾")
        animal["age"] = age_string(animal.get("birthdate") or "", today)
        return animal

    # ------------------------------------------------------------------
    # Static frontend
    # ------------------------------------------------------------------

    @app.get("/")
    def index():
        return send_from_directory("web", "index.html")

    # ------------------------------------------------------------------
    # Meta
    # ------------------------------------------------------------------

    @app.get("/api/meta")
    def meta():
        animals = [enrich_animal(a) for a in db.list_animals()]
        return jsonify({
            "animals": animals,
            "persons": persons,
            "daily_food_target_g": config["daily_food_target_g"],
            "health_reminder_days": config["health_reminder_days"],
            "species_options": db.SPECIES_OPTIONS,
        })

    # ------------------------------------------------------------------
    # Animals
    # ------------------------------------------------------------------

    @app.get("/api/animals")
    def get_animals():
        return jsonify([enrich_animal(a) for a in db.list_animals()])

    @app.post("/api/animals")
    def post_animal():
        body = request.get_json(silent=True) or {}
        name = (body.get("name") or "").strip()
        if not name:
            return jsonify({"error": "Name ist erforderlich"}), 400
        species = body.get("species", "dog")
        if species not in db.SPECIES_OPTIONS:
            return jsonify({"error": "Ungültige Tierart"}), 400
        animal = db.create_animal(name, species, body.get("birthdate") or None)
        return jsonify(enrich_animal(animal)), 201

    @app.patch("/api/animals/<int:animal_id>")
    def patch_animal(animal_id):
        if not db.get_animal(animal_id):
            return jsonify({"error": "Tier nicht gefunden"}), 404
        body = request.get_json(silent=True) or {}
        fields = {}
        if "name" in body:
            name = (body["name"] or "").strip()
            if not name:
                return jsonify({"error": "Name ist erforderlich"}), 400
            fields["name"] = name
        if "species" in body:
            if body["species"] not in db.SPECIES_OPTIONS:
                return jsonify({"error": "Ungültige Tierart"}), 400
            fields["species"] = body["species"]
        if "birthdate" in body:
            fields["birthdate"] = body["birthdate"] or None
        return jsonify(enrich_animal(db.update_animal(animal_id, **fields)))

    @app.delete("/api/animals/<int:animal_id>")
    def delete_animal_route(animal_id):
        if not db.get_animal(animal_id):
            return jsonify({"error": "Tier nicht gefunden"}), 404
        db.delete_animal(animal_id)
        return "", 204

    # ------------------------------------------------------------------
    # Dashboard
    # ------------------------------------------------------------------

    @app.get("/api/dashboard")
    def dashboard():
        now_utc = datetime.datetime.now(UTC)
        today = now_utc.astimezone(LOCAL_TZ).date()
        day_start, day_end = local_day_bounds_utc(now_utc)
        animal_id = request.args.get("animal_id", type=int)

        food_today = db.food_total_today(day_start, day_end, animal_id)

        horizon = (today + datetime.timedelta(days=config["health_reminder_days"])).isoformat()
        upcoming = db.upcoming_health(today.isoformat(), horizon, animal_id)
        for item in upcoming:
            item["due_date"] = next_due_date(item["due_date"], item["repeat_weeks"])
            item["overdue"] = item["due_date"] < today.isoformat()

        weights = db.list_weights(animal_id)
        weight_history = [{"date": w["date"], "weight_kg": w["weight_kg"]} for w in weights[-20:]]
        latest = db.latest_weight(animal_id)

        animal = db.get_animal(animal_id) if animal_id else None
        if animal:
            enrich_animal(animal)

        return jsonify({
            "animal": animal,
            "persons": persons,
            "feeding": {
                "today_g": food_today,
                "target_g": config["daily_food_target_g"],
            },
            "upcoming_health": upcoming,
            "weight": {
                "latest": latest,
                "history": weight_history,
            },
        })

    @app.get("/api/ha-sensors")
    def ha_sensors():
        now_utc = datetime.datetime.now(UTC)
        today = now_utc.astimezone(LOCAL_TZ).date()
        day_start, day_end = local_day_bounds_utc(now_utc)

        animals = db.list_animals()
        primary_id = animals[0]["id"] if animals else None

        food_today = db.food_total_today(day_start, day_end, primary_id)

        horizon = (today + datetime.timedelta(days=config["health_reminder_days"])).isoformat()
        upcoming = db.upcoming_health(today.isoformat(), horizon)
        next_due = None
        if upcoming:
            sorted_up = sorted(
                upcoming, key=lambda e: next_due_date(e["due_date"], e["repeat_weeks"]) or "9999"
            )
            first = sorted_up[0]
            next_due = {
                "title": first["title"],
                "type": first["type"],
                "due_date": next_due_date(first["due_date"], first["repeat_weeks"]),
            }

        return jsonify({
            "fed_today_g": food_today,
            "next_due_health": next_due,
        })

    # ------------------------------------------------------------------
    # Feedings
    # ------------------------------------------------------------------

    @app.get("/api/feedings")
    def get_feedings():
        limit = request.args.get("limit", type=int)
        animal_id = request.args.get("animal_id", type=int)
        return jsonify({
            "items": db.list_feedings(animal_id=animal_id, limit=limit),
            "suggestions": db.recent_food_types(animal_id=animal_id),
        })

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
        feeding = db.create_feeding(ts_utc, person, food_type, amount_g, body.get("animal_id"))
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
        animal_id = request.args.get("animal_id", type=int)
        items = db.list_weights(animal_id=animal_id)
        animal = db.get_animal(animal_id) if animal_id else None
        birthdate = (animal or {}).get("birthdate") or ""
        for item in items:
            try:
                d = datetime.date.fromisoformat(item["date"])
                bd = datetime.date.fromisoformat(birthdate)
                item["age_weeks"] = (d - bd).days // 7 if d >= bd else None
            except (ValueError, TypeError):
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

        weight = db.create_weight(date, weight_kg, person, body.get("animal_id"))
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
        animal_id = request.args.get("animal_id", type=int)
        event_type = request.args.get("type")
        items = db.list_health(animal_id=animal_id, event_type=event_type)
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

        event = db.create_health(event_type, title, date, note, due_date, repeat_weeks, person, body.get("animal_id"))
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
        return jsonify(db.update_health(event_id, **fields))

    @app.delete("/api/health/<int:event_id>")
    def delete_health(event_id):
        if not db.get_health(event_id):
            return jsonify({"error": "Eintrag nicht gefunden"}), 404
        db.delete_health(event_id)
        return "", 204

    return app

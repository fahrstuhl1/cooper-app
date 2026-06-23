"""Flask-Routen für Cooper."""
import calendar
import datetime
import logging
from zoneinfo import ZoneInfo

from flask import Flask, jsonify, request, send_from_directory

import db
import notifier

UTC = datetime.timezone.utc

log = logging.getLogger("cooper")

SPECIES_ICONS = {"dog": "🐕", "cat": "🐱", "rabbit": "🐇", "bird": "🐦", "reptile": "🦎", "other": "🐾"}


def create_app(config):
    app = Flask(__name__, static_folder=None)
    LOCAL_TZ = ZoneInfo(config.get("timezone", "Europe/Berlin"))

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

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

    def enrich_product(p):
        today = datetime.datetime.now(LOCAL_TZ).date()
        daily = p.get("daily_portion_g") or 1
        stock_g = p.get("stock_g") or 0
        pkg_w = p.get("package_weight_g") or 1
        unit = p.get("unit") or "g"
        days_remaining = round(stock_g / daily, 1) if daily > 0 else 0
        buy_ahead = p.get("buy_ahead_days") or 10
        p["days_remaining"] = days_remaining
        p["run_out_date"] = (today + datetime.timedelta(days=int(days_remaining))).isoformat()
        p["needs_buying"] = days_remaining <= buy_ahead
        p["status"] = "critical" if days_remaining <= 0 else "low" if p["needs_buying"] else "ok"
        p["packages_remaining"] = round(stock_g / pkg_w, 2) if pkg_w else 0
        is_piece_based = unit in ("Dose", "Stück")
        p["is_piece_based"] = is_piece_based
        if is_piece_based and pkg_w:
            p["display_daily_count"] = round(daily / pkg_w, 2)
            p["display_stock_count"] = round(stock_g / pkg_w, 2)
        return p

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
        animal_id = request.args.get("animal_id", type=int)

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

        food_reminders = [enrich_product(p) for p in db.low_stock_products(animal_id)]

        return jsonify({
            "animal": animal,
            "upcoming_health": upcoming,
            "weight": {
                "latest": latest,
                "history": weight_history,
            },
            "food_reminders": food_reminders,
        })

    @app.get("/api/ha-sensors")
    def ha_sensors():
        now_utc = datetime.datetime.now(UTC)
        today = now_utc.astimezone(LOCAL_TZ).date()

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
            "next_due_health": next_due,
        })

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
        date = body.get("date") or datetime.datetime.now(LOCAL_TZ).date().isoformat()
        weight_kg = body.get("weight_kg")
        if weight_kg is None:
            return jsonify({"error": "Gewicht ist erforderlich"}), 400
        try:
            weight_kg = round(float(weight_kg), 2)
        except (TypeError, ValueError):
            return jsonify({"error": "Gewicht muss eine Zahl sein"}), 400

        weight = db.create_weight(date, weight_kg, None, body.get("animal_id"))
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

        event = db.create_health(event_type, title, date, note, due_date, repeat_weeks, None, body.get("animal_id"))
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
        for key in ("title", "date", "note", "due_date", "repeat_weeks", "animal_id"):
            if key in body:
                fields[key] = body[key]
        return jsonify(db.update_health(event_id, **fields))

    @app.delete("/api/health/<int:event_id>")
    def delete_health(event_id):
        if not db.get_health(event_id):
            return jsonify({"error": "Eintrag nicht gefunden"}), 404
        db.delete_health(event_id)
        return "", 204

    # ------------------------------------------------------------------
    # Food products
    # ------------------------------------------------------------------

    @app.get("/api/food-products")
    def get_food_products():
        animal_id = request.args.get("animal_id", type=int)
        return jsonify([enrich_product(p) for p in db.list_food_products(animal_id=animal_id)])

    @app.post("/api/food-products")
    def post_food_product():
        body = request.get_json(silent=True) or {}
        name = (body.get("name") or "").strip()
        if not name:
            return jsonify({"error": "Name ist erforderlich"}), 400
        try:
            package_weight_g = int(body.get("package_weight_g") or 0)
            daily_portion_g = int(body.get("daily_portion_g") or 0)
            initial_packages = float(body.get("initial_packages") or 0)
            buy_ahead_days = int(body.get("buy_ahead_days") or 10)
        except (TypeError, ValueError):
            return jsonify({"error": "Ungültige Zahlenwerte"}), 400
        if package_weight_g <= 0 or daily_portion_g <= 0:
            return jsonify({"error": "Packungsgröße und Tagesration müssen > 0 sein"}), 400
        note = body.get("note") or None
        unit = body.get("unit") or "g"
        animal_id = None if body.get("shared") else body.get("animal_id")
        product = db.create_food_product(animal_id, name, package_weight_g, daily_portion_g, initial_packages, buy_ahead_days, note, unit)
        return jsonify(enrich_product(product)), 201

    @app.patch("/api/food-products/<int:product_id>")
    def patch_food_product(product_id):
        if not db.get_food_product(product_id):
            return jsonify({"error": "Produkt nicht gefunden"}), 404
        body = request.get_json(silent=True) or {}
        fields = {}
        if "name" in body:
            name = (body["name"] or "").strip()
            if not name:
                return jsonify({"error": "Name ist erforderlich"}), 400
            fields["name"] = name
        for key in ("package_weight_g", "daily_portion_g", "buy_ahead_days"):
            if key in body:
                try:
                    fields[key] = int(body[key])
                except (TypeError, ValueError):
                    return jsonify({"error": f"Ungültiger Wert für {key}"}), 400
        if "note" in body:
            fields["note"] = body["note"] or None
        if "unit" in body:
            fields["unit"] = body["unit"] or "g"
        if "shared" in body:
            fields["animal_id"] = None
        elif "animal_id" in body:
            fields["animal_id"] = body["animal_id"]
        return jsonify(enrich_product(db.update_food_product(product_id, **fields)))

    @app.delete("/api/food-products/<int:product_id>")
    def delete_food_product_route(product_id):
        if not db.get_food_product(product_id):
            return jsonify({"error": "Produkt nicht gefunden"}), 404
        db.delete_food_product(product_id)
        return "", 204

    # ------------------------------------------------------------------
    # Notifications
    # ------------------------------------------------------------------

    @app.post("/api/notify-test")
    def notify_test():
        ok = notifier.check_and_notify(config)
        if ok:
            return jsonify({"status": "sent"})
        return jsonify({"status": "skipped", "reason": "Nichts zu senden oder kein SUPERVISOR_TOKEN"})

    @app.post("/api/food-products/<int:product_id>/restock")
    def restock_food_product_route(product_id):
        if not db.get_food_product(product_id):
            return jsonify({"error": "Produkt nicht gefunden"}), 404
        body = request.get_json(silent=True) or {}
        try:
            packages = float(body.get("packages") or 0)
        except (TypeError, ValueError):
            return jsonify({"error": "Ungültige Anzahl Pakete"}), 400
        if packages <= 0:
            return jsonify({"error": "Anzahl muss > 0 sein"}), 400
        product = db.restock_food_product(product_id, packages)
        return jsonify(enrich_product(product))

    return app

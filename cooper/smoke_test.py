"""Smoke-Test für Cooper: Routen per Flask-Testclient prüfen.

Aufruf: python3 smoke_test.py
"""
import json
import os
import sys
import tempfile

APP_DIR = os.path.join(os.path.dirname(__file__), "app")
sys.path.insert(0, APP_DIR)


def main():
    tmpdir = tempfile.mkdtemp()
    db_path = os.path.join(tmpdir, "cooper.db")
    options_path = os.path.join(tmpdir, "options.json")

    with open(options_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "dog_name": "Cooper",
                "birthdate": "2025-09-13",
                "persons": ["Max", "Franzi"],
                "daily_food_target_g": 300,
                "health_reminder_days": 30,
                "log_level": "debug",
            },
            f,
        )

    os.environ["COOPER_DB_PATH"] = db_path
    os.environ["COOPER_OPTIONS_PATH"] = options_path

    import db
    from config import load_config
    from server import create_app

    config = load_config()
    db.init_db()
    app = create_app(config)
    client = app.test_client()

    def check(label, condition):
        status = "OK" if condition else "FAIL"
        print(f"[{status}] {label}")
        if not condition:
            raise SystemExit(1)

    # --- meta ---------------------------------------------------------
    r = client.get("/api/meta")
    check("GET /api/meta", r.status_code == 200)
    meta = r.get_json()
    check("meta enthält persons", meta["persons"] == ["Max", "Franzi"])
    check("meta enthält Alter", "age" in meta and meta["age"])

    # --- dashboard (leer) ----------------------------------------------
    r = client.get("/api/dashboard")
    check("GET /api/dashboard (leer)", r.status_code == 200)
    dash = r.get_json()
    check("walks.minutes_since_last ist None", dash["walks"]["minutes_since_last"] is None)
    check("feeding.target_g korrekt", dash["feeding"]["target_g"] == 300)
    check("commands seed vorhanden", dash["commands"]["total"] > 0)

    # --- walks -----------------------------------------------------------
    r = client.post("/api/walks", json={"person": "Max", "pee": True, "poop": False, "note": "Quick-Log"})
    check("POST /api/walks", r.status_code == 201)
    walk = r.get_json()
    walk_id = walk["id"]
    check("Walk hat Person Max", walk["person"] == "Max")

    r = client.post("/api/walks", json={"person": "Unbekannt", "pee": True})
    check("POST /api/walks mit unbekannter Person -> 400", r.status_code == 400)

    r = client.patch(f"/api/walks/{walk_id}", json={"poop": True, "note": "editiert"})
    check("PATCH /api/walks/<id>", r.status_code == 200 and r.get_json()["poop"] == 1)

    r = client.get("/api/dashboard")
    dash = r.get_json()
    check("walks.minutes_since_last gesetzt", dash["walks"]["minutes_since_last"] is not None)
    check("walks.minutes_since_pee gesetzt", dash["walks"]["minutes_since_pee"] is not None)
    check("walks.minutes_since_poop gesetzt", dash["walks"]["minutes_since_poop"] is not None)
    check("walks.today_count == 1", dash["walks"]["today_count"] == 1)

    r = client.delete(f"/api/walks/{walk_id}")
    check("DELETE /api/walks/<id>", r.status_code == 204)
    r = client.delete(f"/api/walks/{walk_id}")
    check("DELETE /api/walks/<id> erneut -> 404", r.status_code == 404)

    # --- feedings ---------------------------------------------------------
    r = client.post("/api/feedings", json={"person": "Franzi", "food_type": "Trockenfutter", "amount_g": 80})
    check("POST /api/feedings", r.status_code == 201)
    feeding_id = r.get_json()["id"]

    r = client.get("/api/feedings")
    body = r.get_json()
    check("GET /api/feedings liefert suggestions", "Trockenfutter" in body["suggestions"])

    r = client.get("/api/dashboard")
    dash = r.get_json()
    check("feeding.today_g == 80", dash["feeding"]["today_g"] == 80)

    r = client.delete(f"/api/feedings/{feeding_id}")
    check("DELETE /api/feedings/<id>", r.status_code == 204)

    # --- weights -----------------------------------------------------------
    r = client.post("/api/weights", json={"person": "Max", "date": "2025-12-06", "weight_kg": 3.45})
    check("POST /api/weights", r.status_code == 201)
    weight_id = r.get_json()["id"]
    check("Gewicht hat 2 Dezimalstellen", r.get_json()["weight_kg"] == 3.45)

    r = client.get("/api/weights")
    items = r.get_json()
    check("GET /api/weights enthält age_weeks", items[0]["age_weeks"] is not None)

    r = client.get("/api/dashboard")
    dash = r.get_json()
    check("dashboard.weight.latest gesetzt", dash["weight"]["latest"]["weight_kg"] == 3.45)

    r = client.delete(f"/api/weights/{weight_id}")
    check("DELETE /api/weights/<id>", r.status_code == 204)

    # --- health ------------------------------------------------------------
    r = client.post(
        "/api/health",
        json={
            "type": "Wurmkur",
            "title": "Entwurmung",
            "date": "2026-05-01",
            "repeat_weeks": 4,
            "person": "Franzi",
        },
    )
    check("POST /api/health", r.status_code == 201)
    health_id = r.get_json()["id"]

    r = client.post("/api/health", json={"type": "Ungültig", "title": "X", "date": "2026-05-01"})
    check("POST /api/health mit ungültigem Typ -> 400", r.status_code == 400)

    r = client.get("/api/dashboard")
    dash = r.get_json()
    check("upcoming_health enthält Eintrag", len(dash["upcoming_health"]) >= 1)
    check("upcoming_health overdue gesetzt", "overdue" in dash["upcoming_health"][0])

    r = client.patch(f"/api/health/{health_id}", json={"note": "aktualisiert"})
    check("PATCH /api/health/<id>", r.status_code == 200 and r.get_json()["note"] == "aktualisiert")

    r = client.delete(f"/api/health/{health_id}")
    check("DELETE /api/health/<id>", r.status_code == 204)

    # --- commands ------------------------------------------------------------
    r = client.get("/api/commands")
    commands = r.get_json()
    check("Kommandos seed vorhanden", len(commands) > 0)
    command_id = commands[0]["id"]

    r = client.patch(f"/api/commands/{command_id}")
    check("PATCH /api/commands/<id> ohne Status -> nächster Status", r.get_json()["status"] == "in Arbeit")

    r = client.patch(f"/api/commands/{command_id}", json={"status": "sitzt"})
    check("PATCH /api/commands/<id> mit Status", r.get_json()["status"] == "sitzt")

    r = client.get("/api/dashboard")
    dash = r.get_json()
    check("commands.done == 1", dash["commands"]["done"] == 1)

    # --- sessions ------------------------------------------------------------
    r = client.post(
        "/api/sessions",
        json={"person": "Max", "date": "2026-06-12", "duration_min": 10, "commands": [command_id], "note": "Übung"},
    )
    check("POST /api/sessions", r.status_code == 201)

    r = client.get("/api/sessions")
    check("GET /api/sessions liefert Liste", len(r.get_json()) == 1)

    # --- ha-sensors ------------------------------------------------------------
    r = client.get("/api/ha-sensors")
    check("GET /api/ha-sensors", r.status_code == 200)
    sensors = r.get_json()
    check("ha-sensors enthält fed_today_g", "fed_today_g" in sensors)
    check("ha-sensors enthält next_due_health", "next_due_health" in sensors)

    # --- index.html ------------------------------------------------------------
    r = client.get("/")
    check("GET / liefert index.html", r.status_code == 200 and b"<html" in r.data.lower())

    print("\nAlle Smoke-Tests erfolgreich.")


if __name__ == "__main__":
    main()

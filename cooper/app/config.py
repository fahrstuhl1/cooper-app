"""Lädt die Add-on-Optionen aus /data/options.json mit sinnvollen Defaults."""
import json
import os

DEFAULTS = {
    "dog_name": "Cooper",
    "birthdate": "2025-09-13",
    "persons": ["Max", "Franzi"],
    "daily_food_target_g": 300,
    "health_reminder_days": 30,
    "log_level": "info",
}

OPTIONS_PATH = os.environ.get("COOPER_OPTIONS_PATH", "/data/options.json")


def load_config():
    config = dict(DEFAULTS)
    if os.path.exists(OPTIONS_PATH):
        try:
            with open(OPTIONS_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            for key in DEFAULTS:
                if key in data and data[key] not in (None, ""):
                    config[key] = data[key]
        except (json.JSONDecodeError, OSError):
            pass

    if not isinstance(config.get("persons"), list) or not config["persons"]:
        config["persons"] = DEFAULTS["persons"]

    return config

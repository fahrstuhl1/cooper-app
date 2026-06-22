"""Lädt die Add-on-Optionen aus /data/options.json mit sinnvollen Defaults."""
import json
import os

DEFAULTS = {
    "animals": [
        {"name": "Cooper", "species": "dog", "birthdate": "2025-09-13"},
        {"name": "Katze 1", "species": "cat", "birthdate": ""},
        {"name": "Katze 2", "species": "cat", "birthdate": ""},
    ],
    "health_reminder_days": 30,
    "notification_service": "notify",
    "notify_hour": 8,
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

    if not isinstance(config.get("animals"), list) or not config["animals"]:
        config["animals"] = DEFAULTS["animals"]

    return config

"""Entrypoint: lädt Config, initialisiert DB und startet waitress."""
import logging

from waitress import serve

import db
from config import load_config
from server import create_app

LOG_LEVELS = {
    "debug": logging.DEBUG,
    "info": logging.INFO,
    "warning": logging.WARNING,
    "error": logging.ERROR,
}


def main():
    config = load_config()
    logging.basicConfig(
        level=LOG_LEVELS.get(config["log_level"], logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    log = logging.getLogger("cooper")
    log.info("Starte Cooper für %s (geb. %s)", config["dog_name"], config["birthdate"])

    db.init_db()

    app = create_app(config)
    serve(app, host="0.0.0.0", port=8099)


if __name__ == "__main__":
    main()

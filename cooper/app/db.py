"""SQLite-Datenschicht für den Tier-Gesundheitstracker. WAL-Modus, CREATE TABLE IF NOT EXISTS."""
import datetime
import os
import sqlite3
import threading

DB_PATH = os.environ.get("COOPER_DB_PATH", "/data/cooper.db")

_local = threading.local()

SPECIES_OPTIONS = ["dog", "cat", "rabbit", "bird", "reptile", "other"]


def utcnow_iso():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def get_conn():
    conn = getattr(_local, "conn", None)
    if conn is None:
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        _local.conn = conn
    return conn


def init_db():
    conn = get_conn()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS animals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            species TEXT NOT NULL DEFAULT 'dog',
            birthdate TEXT,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS feedings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts_utc TEXT NOT NULL,
            person TEXT NOT NULL,
            food_type TEXT NOT NULL,
            amount_g INTEGER NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS weights (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            weight_kg REAL NOT NULL,
            person TEXT,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS health_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT NOT NULL,
            title TEXT NOT NULL,
            date TEXT NOT NULL,
            note TEXT,
            due_date TEXT,
            repeat_weeks INTEGER,
            person TEXT,
            created_at TEXT NOT NULL
        );
        """
    )
    conn.commit()

    # Migrations: add animal_id if column doesn't exist yet
    for table in ("feedings", "weights", "health_events"):
        cols = [row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()]
        if "animal_id" not in cols:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN animal_id INTEGER REFERENCES animals(id)")
    conn.commit()


def seed_animals(initial_animals):
    """Befüllt Tiere beim ersten Start. Weist verwaiste Datensätze dem ersten Tier zu."""
    conn = get_conn()
    cur = conn.execute("SELECT COUNT(*) AS c FROM animals")
    if cur.fetchone()["c"] > 0:
        return
    now = utcnow_iso()
    for a in initial_animals:
        conn.execute(
            "INSERT INTO animals (name, species, birthdate, created_at) VALUES (?, ?, ?, ?)",
            (a["name"], a.get("species", "dog"), a.get("birthdate") or None, now),
        )
    conn.commit()
    first = conn.execute("SELECT id FROM animals ORDER BY id ASC LIMIT 1").fetchone()
    if first:
        for table in ("feedings", "weights", "health_events"):
            conn.execute(
                f"UPDATE {table} SET animal_id = ? WHERE animal_id IS NULL",
                (first["id"],),
            )
    conn.commit()


# ---------------------------------------------------------------------------
# Animals
# ---------------------------------------------------------------------------

def list_animals():
    conn = get_conn()
    return [dict(r) for r in conn.execute("SELECT * FROM animals ORDER BY id ASC").fetchall()]


def get_animal(animal_id):
    conn = get_conn()
    row = conn.execute("SELECT * FROM animals WHERE id = ?", (animal_id,)).fetchone()
    return dict(row) if row else None


def create_animal(name, species, birthdate):
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO animals (name, species, birthdate, created_at) VALUES (?, ?, ?, ?)",
        (name, species, birthdate or None, utcnow_iso()),
    )
    conn.commit()
    return get_animal(cur.lastrowid)


def update_animal(animal_id, **fields):
    conn = get_conn()
    allowed = {"name", "species", "birthdate"}
    sets, values = [], []
    for key, value in fields.items():
        if key in allowed:
            sets.append(f"{key} = ?")
            values.append(value)
    if not sets:
        return get_animal(animal_id)
    values.append(animal_id)
    conn.execute(f"UPDATE animals SET {', '.join(sets)} WHERE id = ?", values)
    conn.commit()
    return get_animal(animal_id)


def delete_animal(animal_id):
    conn = get_conn()
    conn.execute("DELETE FROM animals WHERE id = ?", (animal_id,))
    conn.commit()


# ---------------------------------------------------------------------------
# Feedings
# ---------------------------------------------------------------------------

def list_feedings(animal_id=None, limit=None):
    conn = get_conn()
    if animal_id:
        q = "SELECT * FROM feedings WHERE animal_id = ? ORDER BY ts_utc DESC, id DESC"
        args = [animal_id]
    else:
        q = "SELECT * FROM feedings ORDER BY ts_utc DESC, id DESC"
        args = []
    if limit:
        q += f" LIMIT {int(limit)}"
    return [dict(r) for r in conn.execute(q, args).fetchall()]


def get_feeding(feeding_id):
    conn = get_conn()
    row = conn.execute("SELECT * FROM feedings WHERE id = ?", (feeding_id,)).fetchone()
    return dict(row) if row else None


def create_feeding(ts_utc, person, food_type, amount_g, animal_id=None):
    conn = get_conn()
    cur = conn.execute(
        """INSERT INTO feedings (ts_utc, person, food_type, amount_g, animal_id, created_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (ts_utc, person, food_type, int(amount_g), animal_id, utcnow_iso()),
    )
    conn.commit()
    return get_feeding(cur.lastrowid)


def delete_feeding(feeding_id):
    conn = get_conn()
    conn.execute("DELETE FROM feedings WHERE id = ?", (feeding_id,))
    conn.commit()


def food_total_today(day_start_utc, day_end_utc, animal_id=None):
    conn = get_conn()
    if animal_id:
        row = conn.execute(
            """SELECT COALESCE(SUM(amount_g), 0) AS total FROM feedings
               WHERE ts_utc >= ? AND ts_utc < ? AND animal_id = ?""",
            (day_start_utc, day_end_utc, animal_id),
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT COALESCE(SUM(amount_g), 0) AS total FROM feedings WHERE ts_utc >= ? AND ts_utc < ?",
            (day_start_utc, day_end_utc),
        ).fetchone()
    return row["total"]


def recent_food_types(animal_id=None, limit=8):
    conn = get_conn()
    if animal_id:
        rows = conn.execute(
            "SELECT DISTINCT food_type FROM feedings WHERE animal_id = ? ORDER BY id DESC LIMIT 50",
            (animal_id,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT DISTINCT food_type FROM feedings ORDER BY id DESC LIMIT 50"
        ).fetchall()
    seen = []
    for r in rows:
        if r["food_type"] not in seen:
            seen.append(r["food_type"])
        if len(seen) >= limit:
            break
    return seen


# ---------------------------------------------------------------------------
# Weights
# ---------------------------------------------------------------------------

def list_weights(animal_id=None):
    conn = get_conn()
    if animal_id:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM weights WHERE animal_id = ? ORDER BY date ASC, id ASC", (animal_id,)
        ).fetchall()]
    return [dict(r) for r in conn.execute(
        "SELECT * FROM weights ORDER BY date ASC, id ASC"
    ).fetchall()]


def get_weight(weight_id):
    conn = get_conn()
    row = conn.execute("SELECT * FROM weights WHERE id = ?", (weight_id,)).fetchone()
    return dict(row) if row else None


def create_weight(date, weight_kg, person, animal_id=None):
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO weights (date, weight_kg, person, animal_id, created_at) VALUES (?, ?, ?, ?, ?)",
        (date, float(weight_kg), person, animal_id, utcnow_iso()),
    )
    conn.commit()
    return get_weight(cur.lastrowid)


def delete_weight(weight_id):
    conn = get_conn()
    conn.execute("DELETE FROM weights WHERE id = ?", (weight_id,))
    conn.commit()


def latest_weight(animal_id=None):
    conn = get_conn()
    if animal_id:
        row = conn.execute(
            "SELECT * FROM weights WHERE animal_id = ? ORDER BY date DESC, id DESC LIMIT 1",
            (animal_id,),
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT * FROM weights ORDER BY date DESC, id DESC LIMIT 1"
        ).fetchone()
    return dict(row) if row else None


# ---------------------------------------------------------------------------
# Health events
# ---------------------------------------------------------------------------

def list_health(animal_id=None, event_type=None):
    conn = get_conn()
    conditions, args = [], []
    if animal_id:
        conditions.append("animal_id = ?")
        args.append(animal_id)
    if event_type:
        conditions.append("type = ?")
        args.append(event_type)
    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    rows = conn.execute(
        f"SELECT * FROM health_events {where} ORDER BY date DESC, id DESC", args
    ).fetchall()
    return [dict(r) for r in rows]


def get_health(event_id):
    conn = get_conn()
    row = conn.execute("SELECT * FROM health_events WHERE id = ?", (event_id,)).fetchone()
    return dict(row) if row else None


def create_health(event_type, title, date, note, due_date, repeat_weeks, person, animal_id=None):
    conn = get_conn()
    cur = conn.execute(
        """INSERT INTO health_events (type, title, date, note, due_date, repeat_weeks, person, animal_id, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (event_type, title, date, note, due_date, repeat_weeks, person, animal_id, utcnow_iso()),
    )
    conn.commit()
    return get_health(cur.lastrowid)


def update_health(event_id, **fields):
    conn = get_conn()
    allowed = {"type", "title", "date", "note", "due_date", "repeat_weeks", "person"}
    sets, values = [], []
    for key, value in fields.items():
        if key in allowed:
            sets.append(f"{key} = ?")
            values.append(value)
    if not sets:
        return get_health(event_id)
    values.append(event_id)
    conn.execute(f"UPDATE health_events SET {', '.join(sets)} WHERE id = ?", values)
    conn.commit()
    return get_health(event_id)


def delete_health(event_id):
    conn = get_conn()
    conn.execute("DELETE FROM health_events WHERE id = ?", (event_id,))
    conn.commit()


def upcoming_health(today_iso, horizon_date_iso, animal_id=None):
    """Liefert Einträge mit Fälligkeit <= horizon_date_iso (inkl. überfällig)."""
    conn = get_conn()
    conditions = ["due_date IS NOT NULL", "due_date != ''", "due_date <= ?"]
    args = [horizon_date_iso]
    if animal_id:
        conditions.append("animal_id = ?")
        args.append(animal_id)
    rows = conn.execute(
        f"SELECT * FROM health_events WHERE {' AND '.join(conditions)} ORDER BY due_date ASC",
        args,
    ).fetchall()
    result = []
    for r in rows:
        item = dict(r)
        item["overdue"] = item["due_date"] < today_iso
        result.append(item)
    return result

"""SQLite-Datenschicht für Cooper. WAL-Modus, CREATE TABLE IF NOT EXISTS."""
import datetime
import json
import os
import sqlite3
import threading

DB_PATH = os.environ.get("COOPER_DB_PATH", "/data/cooper.db")

_local = threading.local()

DEFAULT_COMMANDS = [
    "Sitz",
    "Platz",
    "Bleib",
    "Hier/Komm",
    "Nein/Aus",
    "Fuß",
    "Pfote",
    "Aus der Leine warten",
]


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
        CREATE TABLE IF NOT EXISTS walks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts_utc TEXT NOT NULL,
            person TEXT NOT NULL,
            pee INTEGER NOT NULL DEFAULT 0,
            poop INTEGER NOT NULL DEFAULT 0,
            duration_min INTEGER,
            note TEXT,
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

        CREATE TABLE IF NOT EXISTS commands (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            status TEXT NOT NULL DEFAULT 'neu',
            status_changed_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS training_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            person TEXT NOT NULL,
            duration_min INTEGER,
            note TEXT,
            commands TEXT NOT NULL DEFAULT '[]',
            created_at TEXT NOT NULL
        );
        """
    )
    conn.commit()

    cur = conn.execute("SELECT COUNT(*) AS c FROM commands")
    if cur.fetchone()["c"] == 0:
        now = utcnow_iso()
        conn.executemany(
            "INSERT INTO commands (name, status, status_changed_at) VALUES (?, 'neu', ?)",
            [(name, now) for name in DEFAULT_COMMANDS],
        )
        conn.commit()


# ---------------------------------------------------------------------------
# Walks
# ---------------------------------------------------------------------------

def list_walks(limit=None):
    conn = get_conn()
    q = "SELECT * FROM walks ORDER BY ts_utc DESC, id DESC"
    if limit:
        q += f" LIMIT {int(limit)}"
    return [dict(r) for r in conn.execute(q).fetchall()]


def get_walk(walk_id):
    conn = get_conn()
    row = conn.execute("SELECT * FROM walks WHERE id = ?", (walk_id,)).fetchone()
    return dict(row) if row else None


def create_walk(ts_utc, person, pee, poop, duration_min, note):
    conn = get_conn()
    cur = conn.execute(
        """INSERT INTO walks (ts_utc, person, pee, poop, duration_min, note, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (ts_utc, person, int(pee), int(poop), duration_min, note, utcnow_iso()),
    )
    conn.commit()
    return get_walk(cur.lastrowid)


def update_walk(walk_id, **fields):
    conn = get_conn()
    allowed = {"ts_utc", "person", "pee", "poop", "duration_min", "note"}
    sets = []
    values = []
    for key, value in fields.items():
        if key in allowed:
            sets.append(f"{key} = ?")
            if key in ("pee", "poop"):
                value = int(value)
            values.append(value)
    if not sets:
        return get_walk(walk_id)
    values.append(walk_id)
    conn.execute(f"UPDATE walks SET {', '.join(sets)} WHERE id = ?", values)
    conn.commit()
    return get_walk(walk_id)


def delete_walk(walk_id):
    conn = get_conn()
    conn.execute("DELETE FROM walks WHERE id = ?", (walk_id,))
    conn.commit()


def last_walk_of_kind(kind=None):
    conn = get_conn()
    if kind == "pee":
        row = conn.execute(
            "SELECT * FROM walks WHERE pee = 1 ORDER BY ts_utc DESC, id DESC LIMIT 1"
        ).fetchone()
    elif kind == "poop":
        row = conn.execute(
            "SELECT * FROM walks WHERE poop = 1 ORDER BY ts_utc DESC, id DESC LIMIT 1"
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT * FROM walks ORDER BY ts_utc DESC, id DESC LIMIT 1"
        ).fetchone()
    return dict(row) if row else None


def count_walks_today(day_start_utc, day_end_utc):
    conn = get_conn()
    row = conn.execute(
        "SELECT COUNT(*) AS c FROM walks WHERE ts_utc >= ? AND ts_utc < ?",
        (day_start_utc, day_end_utc),
    ).fetchone()
    return row["c"]


# ---------------------------------------------------------------------------
# Feedings
# ---------------------------------------------------------------------------

def list_feedings(limit=None):
    conn = get_conn()
    q = "SELECT * FROM feedings ORDER BY ts_utc DESC, id DESC"
    if limit:
        q += f" LIMIT {int(limit)}"
    return [dict(r) for r in conn.execute(q).fetchall()]


def get_feeding(feeding_id):
    conn = get_conn()
    row = conn.execute("SELECT * FROM feedings WHERE id = ?", (feeding_id,)).fetchone()
    return dict(row) if row else None


def create_feeding(ts_utc, person, food_type, amount_g):
    conn = get_conn()
    cur = conn.execute(
        """INSERT INTO feedings (ts_utc, person, food_type, amount_g, created_at)
           VALUES (?, ?, ?, ?, ?)""",
        (ts_utc, person, food_type, int(amount_g), utcnow_iso()),
    )
    conn.commit()
    return get_feeding(cur.lastrowid)


def delete_feeding(feeding_id):
    conn = get_conn()
    conn.execute("DELETE FROM feedings WHERE id = ?", (feeding_id,))
    conn.commit()


def food_total_today(day_start_utc, day_end_utc):
    conn = get_conn()
    row = conn.execute(
        "SELECT COALESCE(SUM(amount_g), 0) AS total FROM feedings WHERE ts_utc >= ? AND ts_utc < ?",
        (day_start_utc, day_end_utc),
    ).fetchone()
    return row["total"]


def recent_food_types(limit=8):
    conn = get_conn()
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

def list_weights():
    conn = get_conn()
    return [dict(r) for r in conn.execute("SELECT * FROM weights ORDER BY date ASC, id ASC").fetchall()]


def get_weight(weight_id):
    conn = get_conn()
    row = conn.execute("SELECT * FROM weights WHERE id = ?", (weight_id,)).fetchone()
    return dict(row) if row else None


def create_weight(date, weight_kg, person):
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO weights (date, weight_kg, person, created_at) VALUES (?, ?, ?, ?)",
        (date, float(weight_kg), person, utcnow_iso()),
    )
    conn.commit()
    return get_weight(cur.lastrowid)


def delete_weight(weight_id):
    conn = get_conn()
    conn.execute("DELETE FROM weights WHERE id = ?", (weight_id,))
    conn.commit()


def latest_weight():
    conn = get_conn()
    row = conn.execute("SELECT * FROM weights ORDER BY date DESC, id DESC LIMIT 1").fetchone()
    return dict(row) if row else None


# ---------------------------------------------------------------------------
# Health events
# ---------------------------------------------------------------------------

def list_health(event_type=None):
    conn = get_conn()
    if event_type:
        rows = conn.execute(
            "SELECT * FROM health_events WHERE type = ? ORDER BY date DESC, id DESC", (event_type,)
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM health_events ORDER BY date DESC, id DESC").fetchall()
    return [dict(r) for r in rows]


def get_health(event_id):
    conn = get_conn()
    row = conn.execute("SELECT * FROM health_events WHERE id = ?", (event_id,)).fetchone()
    return dict(row) if row else None


def create_health(event_type, title, date, note, due_date, repeat_weeks, person):
    conn = get_conn()
    cur = conn.execute(
        """INSERT INTO health_events (type, title, date, note, due_date, repeat_weeks, person, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (event_type, title, date, note, due_date, repeat_weeks, person, utcnow_iso()),
    )
    conn.commit()
    return get_health(cur.lastrowid)


def update_health(event_id, **fields):
    conn = get_conn()
    allowed = {"type", "title", "date", "note", "due_date", "repeat_weeks", "person"}
    sets = []
    values = []
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


def upcoming_health(today_iso, horizon_date_iso):
    """Liefert Einträge mit Fälligkeit <= horizon_date_iso (inkl. überfällig)."""
    conn = get_conn()
    rows = conn.execute(
        """SELECT * FROM health_events
           WHERE due_date IS NOT NULL AND due_date != '' AND due_date <= ?
           ORDER BY due_date ASC""",
        (horizon_date_iso,),
    ).fetchall()
    result = []
    for r in rows:
        item = dict(r)
        item["overdue"] = item["due_date"] < today_iso
        result.append(item)
    return result


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def list_commands():
    conn = get_conn()
    return [dict(r) for r in conn.execute("SELECT * FROM commands ORDER BY id ASC").fetchall()]


def get_command(command_id):
    conn = get_conn()
    row = conn.execute("SELECT * FROM commands WHERE id = ?", (command_id,)).fetchone()
    return dict(row) if row else None


def create_command(name):
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO commands (name, status, status_changed_at) VALUES (?, 'neu', ?)",
        (name, utcnow_iso()),
    )
    conn.commit()
    return get_command(cur.lastrowid)


def update_command_status(command_id, status):
    conn = get_conn()
    conn.execute(
        "UPDATE commands SET status = ?, status_changed_at = ? WHERE id = ?",
        (status, utcnow_iso(), command_id),
    )
    conn.commit()
    return get_command(command_id)


def delete_command(command_id):
    conn = get_conn()
    conn.execute("DELETE FROM commands WHERE id = ?", (command_id,))
    conn.commit()


# ---------------------------------------------------------------------------
# Training sessions
# ---------------------------------------------------------------------------

def list_sessions(limit=None):
    conn = get_conn()
    q = "SELECT * FROM training_sessions ORDER BY date DESC, id DESC"
    if limit:
        q += f" LIMIT {int(limit)}"
    rows = conn.execute(q).fetchall()
    result = []
    for r in rows:
        item = dict(r)
        item["commands"] = json.loads(item["commands"])
        result.append(item)
    return result


def get_session(session_id):
    conn = get_conn()
    row = conn.execute("SELECT * FROM training_sessions WHERE id = ?", (session_id,)).fetchone()
    if not row:
        return None
    item = dict(row)
    item["commands"] = json.loads(item["commands"])
    return item


def create_session(date, person, duration_min, note, commands):
    conn = get_conn()
    cur = conn.execute(
        """INSERT INTO training_sessions (date, person, duration_min, note, commands, created_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (date, person, duration_min, note, json.dumps(commands), utcnow_iso()),
    )
    conn.commit()
    return get_session(cur.lastrowid)

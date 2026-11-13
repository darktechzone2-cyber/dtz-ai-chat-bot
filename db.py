"""SQLite storage: users, per-user chat history, and bot counters.

One file, no server. History is trimmed to the newest exchanges so the
prompt sent to the AI stays small.
"""

import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    first_name TEXT,
    first_seen TEXT DEFAULT (datetime('now')),
    last_seen TEXT DEFAULT (datetime('now')),
    messages INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    role TEXT NOT NULL,
    text TEXT NOT NULL,
    created TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS counters (
    key TEXT PRIMARY KEY,
    value INTEGER DEFAULT 0
);
"""


def connect(path):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    conn.commit()
    return conn


def record_user(conn, user_id, username, first_name):
    conn.execute(
        """INSERT INTO users (user_id, username, first_name, messages)
           VALUES (?, ?, ?, 1)
           ON CONFLICT(user_id) DO UPDATE SET
               username=excluded.username,
               first_name=excluded.first_name,
               last_seen=datetime('now'),
               messages=messages+1""",
        (user_id, username, first_name),
    )
    conn.commit()


def bump_counter(conn, key, by=1):
    conn.execute(
        "INSERT INTO counters (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value=value+?",
        (key, by, by),
    )
    conn.commit()


def add_exchange(conn, user_id, user_text, assistant_text, keep_exchanges=8):
    conn.execute(
        "INSERT INTO history (user_id, role, text) VALUES (?, 'user', ?)",
        (user_id, user_text),
    )
    conn.execute(
        "INSERT INTO history (user_id, role, text) VALUES (?, 'assistant', ?)",
        (user_id, assistant_text),
    )
    conn.commit()
    # Keep only the newest keep_exchanges exchanges (= 2 rows each).
    conn.execute(
        """DELETE FROM history WHERE user_id=? AND id NOT IN (
               SELECT id FROM history WHERE user_id=?
               ORDER BY id DESC LIMIT ?)""",
        (user_id, user_id, keep_exchanges * 2),
    )
    conn.commit()


def get_history(conn, user_id, keep_exchanges=8):
    rows = conn.execute(
        "SELECT role, text FROM history WHERE user_id=? "
        "ORDER BY id DESC LIMIT ?",
        (user_id, keep_exchanges * 2),
    ).fetchall()
    return [(r["role"], r["text"]) for r in reversed(rows)]


def clear_history(conn, user_id):
    conn.execute("DELETE FROM history WHERE user_id=?", (user_id,))
    conn.commit()


def get_stats(conn):
    users = conn.execute("SELECT COUNT(*) AS n FROM users").fetchone()["n"]
    msgs = conn.execute("SELECT COALESCE(SUM(messages),0) AS n FROM users").fetchone()["n"]
    ai_calls = conn.execute(
        "SELECT value FROM counters WHERE key='ai_calls'"
    ).fetchone()
    return {
        "users": users,
        "messages": msgs,
        "ai_calls": ai_calls["value"] if ai_calls else 0,
    }

"""Data access helpers for dashboard backend."""

import sqlite3


def ensure_custom_name_column(conn):
    try:
        conn.execute("SELECT custom_name FROM sessions LIMIT 1")
    except sqlite3.OperationalError:
        conn.execute("ALTER TABLE sessions ADD COLUMN custom_name TEXT")
        conn.commit()


def ensure_has_tool_marker_column(conn):
    try:
        conn.execute("SELECT has_tool_marker FROM turns LIMIT 1")
    except sqlite3.OperationalError:
        conn.execute("ALTER TABLE turns ADD COLUMN has_tool_marker INTEGER DEFAULT 0")
        conn.commit()


def get_session_by_id(conn, session_id):
    return conn.execute(
        "SELECT session_id FROM sessions WHERE session_id = ?",
        (session_id,),
    ).fetchone()


def update_session_custom_name(conn, session_id, custom_name):
    conn.execute(
        "UPDATE sessions SET custom_name = ? WHERE session_id = ?",
        (custom_name, session_id),
    )
    conn.commit()

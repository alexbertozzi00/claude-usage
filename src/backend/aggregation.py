"""Reusable aggregation helpers for CLI and dashboard.

This module keeps SQL snippets and pure transformation helpers centralized so
multiple entry points can share the same data logic.
"""

from datetime import date, datetime, timedelta


SCHEMA_VERSION = "1.0.0"


def parse_period_spec(period, *, today=None, custom_start=None, custom_end=None):
    """Return current/previous equivalent ranges for a period.

    Dates are returned as YYYY-MM-DD strings and are inclusive.
    """
    today = today or date.today()
    if period in ("7d", "14d", "30d"):
        days = int(period[:-1])
        current_end = today
        current_start = today - timedelta(days=days - 1)
    elif period == "custom":
        if not custom_start or not custom_end:
            raise ValueError("custom period requires --start and --end dates")
        current_start = datetime.strptime(custom_start, "%Y-%m-%d").date()
        current_end = datetime.strptime(custom_end, "%Y-%m-%d").date()
        if current_end < current_start:
            raise ValueError("custom period requires end date >= start date")
        days = (current_end - current_start).days + 1
    else:
        raise ValueError("period must be one of: 7d, 14d, 30d, custom")

    previous_end = current_start - timedelta(days=1)
    previous_start = previous_end - timedelta(days=days - 1)

    return {
        "period": period,
        "days": days,
        "current": {
            "start": current_start.isoformat(),
            "end": current_end.isoformat(),
        },
        "previous": {
            "start": previous_start.isoformat(),
            "end": previous_end.isoformat(),
        },
    }


def fetch_model_catalog(conn):
    rows = conn.execute(
        """
        SELECT COALESCE(model, 'unknown') as model
        FROM turns
        GROUP BY model
        ORDER BY SUM(input_tokens + output_tokens) DESC
        """
    ).fetchall()
    return [r["model"] for r in rows]


def fetch_period_summary(conn, start_date, end_date):
    return conn.execute(
        """
        SELECT
            COALESCE(SUM(input_tokens), 0) as input_tokens,
            COALESCE(SUM(output_tokens), 0) as output_tokens,
            COALESCE(SUM(cache_read_tokens), 0) as cache_read_tokens,
            COALESCE(SUM(cache_creation_tokens), 0) as cache_creation_tokens,
            COUNT(*) as turns,
            COUNT(DISTINCT session_id) as sessions
        FROM turns
        WHERE substr(timestamp, 1, 10) BETWEEN ? AND ?
        """,
        (start_date, end_date),
    ).fetchone()


def fetch_top_models(conn, start_date, end_date, *, limit=5):
    return conn.execute(
        """
        SELECT
            COALESCE(model, 'unknown') as model,
            COALESCE(SUM(input_tokens), 0) as input_tokens,
            COALESCE(SUM(output_tokens), 0) as output_tokens,
            COALESCE(SUM(cache_read_tokens), 0) as cache_read_tokens,
            COALESCE(SUM(cache_creation_tokens), 0) as cache_creation_tokens,
            COUNT(*) as turns,
            COUNT(DISTINCT session_id) as sessions
        FROM turns
        WHERE substr(timestamp, 1, 10) BETWEEN ? AND ?
        GROUP BY model
        ORDER BY (input_tokens + output_tokens) DESC
        LIMIT ?
        """,
        (start_date, end_date, limit),
    ).fetchall()


def fetch_top_projects(conn, start_date, end_date, *, limit=5):
    return conn.execute(
        """
        SELECT
            COALESCE(s.project_name, 'unknown') as project,
            COALESCE(SUM(t.input_tokens), 0) as input_tokens,
            COALESCE(SUM(t.output_tokens), 0) as output_tokens,
            COALESCE(SUM(t.cache_read_tokens), 0) as cache_read_tokens,
            COALESCE(SUM(t.cache_creation_tokens), 0) as cache_creation_tokens,
            COUNT(*) as turns,
            COUNT(DISTINCT t.session_id) as sessions
        FROM turns t
        LEFT JOIN sessions s ON s.session_id = t.session_id
        WHERE substr(t.timestamp, 1, 10) BETWEEN ? AND ?
        GROUP BY s.project_name
        ORDER BY (input_tokens + output_tokens) DESC
        LIMIT ?
        """,
        (start_date, end_date, limit),
    ).fetchall()


def rows_to_dicts(rows, key_map):
    """Pure transformation helper: sqlite rows -> stable dict list."""
    out = []
    for row in rows:
        item = {}
        for src, dst in key_map:
            item[dst] = row[src]
        out.append(item)
    return out

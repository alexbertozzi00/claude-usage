"""
dashboard.py - Local web dashboard served on localhost:8080.
"""

import json
import os
import re
import sqlite3
import subprocess
from html import escape
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from datetime import datetime, timezone
from collections import defaultdict
from urllib.parse import parse_qs, unquote, urlparse

from layout_components import render_app_footer, render_app_header

DB_PATH = Path.home() / ".claude" / "usage.db"
IMAGES_DIR = Path(__file__).resolve().parent / "images"
FAVICON_PATH = IMAGES_DIR / "favicon.svg"
LOGOMARCA_PATH = IMAGES_DIR / "logomarca.png"
MAX_CUSTOM_NAME_LENGTH = 80

COMMON_LAYOUT_STYLES = """
  .app-header {
    background: var(--card, #1a1d27);
    border-bottom: 1px solid var(--border, #2a2d3a);
    padding: 16px 24px;
    display: flex;
    gap: 12px;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
  }
  .app-header-main { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
  .app-logo-link { display: inline-flex; align-items: center; }
  .app-logo { display: block; height: 32px; width: auto; object-fit: contain; }
  .app-header-title { margin: 0; font-size: 20px; font-weight: 700; color: var(--text, #e2e8f0); }
  .app-header-subtitle { color: var(--muted, #8892a4); font-size: 12px; }
  .app-header-right { margin-left: auto; display: inline-flex; align-items: center; gap: 10px; }
  .app-back-link {
    color: var(--link, #6aa6ff);
    text-decoration: none;
    border: 1px solid var(--border, #2a2d3a);
    padding: 8px 10px;
    border-radius: 8px;
    font-size: 13px;
  }
  .app-back-link:hover { text-decoration: underline; }
  .app-footer { border-top: 1px solid var(--border, #2a2d3a); padding: 20px 24px; margin-top: 8px; }
  .app-footer-content { max-width: 1400px; margin: 0 auto; text-align: center; }
  .app-footer-content p { color: var(--muted, #8892a4); font-size: 12px; line-height: 1.7; margin: 0; }
  .app-footer-content a { color: var(--link, #6aa6ff); text-decoration: none; }
  .app-footer-content a:hover { text-decoration: underline; }
"""

HEADER_THEME_TOGGLE_HTML = """
<label id="theme-toggle-button" aria-label="Alternar tema entre claro e escuro">
  <input type="checkbox" id="toggle">
  <svg viewBox="0 0 69.667 44" xmlns:xlink="http://www.w3.org/1999/xlink" xmlns="http://www.w3.org/2000/svg">
    <g transform="translate(3.5 3.5)" data-name="Component 15 – 1" id="Component_15_1">
      <g filter="url(#container)" transform="matrix(1, 0, 0, 1, -3.5, -3.5)"><rect fill="#83cbd8" transform="translate(3.5 3.5)" rx="17.5" height="35" width="60.667" data-name="container" id="container"></rect></g>
      <g transform="translate(2.333 2.333)" id="button"><g data-name="sun" id="sun"><g filter="url(#sun-outer)" transform="matrix(1, 0, 0, 1, -5.83, -5.83)"><circle fill="#f8e664" transform="translate(5.83 5.83)" r="15.167" cy="15.167" cx="15.167" data-name="sun-outer" id="sun-outer-2"></circle></g><g filter="url(#sun)" transform="matrix(1, 0, 0, 1, -5.83, -5.83)"><path fill="rgba(246,254,247,0.29)" transform="translate(9.33 9.33)" d="M11.667,0A11.667,11.667,0,1,1,0,11.667,11.667,11.667,0,0,1,11.667,0Z" data-name="sun" id="sun-3"></path></g><circle fill="#fcf4b9" transform="translate(8.167 8.167)" r="7" cy="7" cx="7" id="sun-inner"></circle></g><g data-name="moon" id="moon"><g filter="url(#moon)" transform="matrix(1, 0, 0, 1, -31.5, -5.83)"><circle fill="#cce6ee" transform="translate(31.5 5.83)" r="15.167" cy="15.167" cx="15.167" data-name="moon" id="moon-3"></circle></g><g fill="#a6cad0" transform="translate(-24.415 -1.009)" id="patches"><circle transform="translate(43.009 4.496)" r="2" cy="2" cx="2"></circle><circle transform="translate(39.366 17.952)" r="2" cy="2" cx="2" data-name="patch"></circle><circle transform="translate(33.016 8.044)" r="1" cy="1" cx="1" data-name="patch"></circle><circle transform="translate(51.081 18.888)" r="1" cy="1" cx="1" data-name="patch"></circle><circle transform="translate(33.016 22.503)" r="1" cy="1" cx="1" data-name="patch"></circle><circle transform="translate(50.081 10.53)" r="1.5" cy="1.5" cx="1.5" data-name="patch"></circle></g></g></g>
      <g filter="url(#cloud)" transform="matrix(1, 0, 0, 1, -3.5, -3.5)"><path fill="#fff" transform="translate(-3466.47 -160.94)" d="M3512.81,173.815a4.463,4.463,0,0,1,2.243.62.95.95,0,0,1,.72-1.281,4.852,4.852,0,0,1,2.623.519c.034.02-.5-1.968.281-2.716a2.117,2.117,0,0,1,2.829-.274,1.821,1.821,0,0,1,.854,1.858c.063.037,2.594-.049,3.285,1.273s-.865,2.544-.807,2.626a12.192,12.192,0,0,1,2.278.892c.553.448,1.106,1.992-1.62,2.927a7.742,7.742,0,0,1-3.762-.3c-1.28-.49-1.181-2.65-1.137-2.624s-1.417,2.2-2.623,2.2a4.172,4.172,0,0,1-2.394-1.206,3.825,3.825,0,0,1-2.771.774c-3.429-.46-2.333-3.267-2.2-3.55A3.721,3.721,0,0,1,3512.81,173.815Z" data-name="cloud" id="cloud"></path></g>
      <g fill="#def8ff" transform="translate(3.585 1.325)" id="stars"><path transform="matrix(-1, 0.017, -0.017, -1, 24.231, 3.055)" d="M.774,0,.566.559,0,.539.458.933.25,1.492l.485-.361.458.394L1.024.953,1.509.592.943.572Z"></path><path transform="matrix(-0.777, 0.629, -0.629, -0.777, 23.185, 12.358)" d="M1.341.529.836.472.736,0,.505.46,0,.4.4.729l-.231.46L.605.932l.4.326L.9.786Z" data-name="star"></path><path transform="matrix(0.438, 0.899, -0.899, 0.438, 23.177, 29.735)" d="M.015,1.065.475.9l.285.365L.766.772l.46-.164L.745.494.751,0,.481.407,0,.293.285.658Z" data-name="star"></path><path transform="translate(12.677 0.388) rotate(104)" d="M1.161,1.6,1.059,1,1.574.722.962.607.86,0,.613.572,0,.457.446.881.2,1.454l.516-.274Z" data-name="star"></path><path transform="matrix(-0.07, 0.998, -0.998, -0.07, 11.066, 15.457)" d="M.873,1.648l.114-.62L1.579.945,1.03.62,1.144,0,.706.464.157.139.438.7,0,1.167l.592-.083Z" data-name="star"></path><path transform="translate(8.326 28.061) rotate(11)" d="M.593,0,.638.724,0,.982l.7.211.045.724.36-.64.7.211L1.342.935,1.7.294,1.063.552Z" data-name="star"></path><path transform="translate(5.012 5.962) rotate(172)" d="M.816,0,.5.455,0,.311.323.767l-.312.455.516-.215.323.456L.827.911,1.343.7.839.552Z" data-name="star"></path><path transform="translate(2.218 14.616) rotate(169)" d="M1.261,0,.774.571.114.3.487.967,0,1.538.728,1.32l.372.662.047-.749.728-.218L1.215.749Z" data-name="star"></path></g>
    </g>
  </svg>
</label>
"""


def _format_date(date_str):
    """Convert YYYY-MM-DD -> dd/MM/YYYY when possible."""
    if not date_str:
        return ""
    try:
        return datetime.strptime(date_str[:10], "%Y-%m-%d").strftime("%d/%m/%Y")
    except Exception:
        return date_str


def _format_timestamp(timestamp_str, *, to_local=True, local_tz=None):
    """Convert ISO timestamp -> dd/MM/YYYY HH:MM:SS when possible.

    By default, timezone-aware values are rendered in the local timezone so
    session times match the operator's clock.
    """
    if not timestamp_str:
        return ""
    try:
        normalized = timestamp_str.replace("Z", "+00:00")
        dt = datetime.fromisoformat(normalized)
        if to_local and dt.tzinfo is not None:
            dt = dt.astimezone(local_tz)
        elif dt.tzinfo is not None:
            dt = dt.astimezone(timezone.utc)
        return dt.strftime("%d/%m/%Y %H:%M:%S")
    except Exception:
        try:
            # Fallback for plain YYYY-MM-DD HH:MM[:SS]
            base = timestamp_str[:19].replace("T", " ")
            fmt = "%Y-%m-%d %H:%M:%S" if len(base) >= 19 else "%Y-%m-%d %H:%M"
            return datetime.strptime(base, fmt).strftime("%d/%m/%Y %H:%M:%S")
        except Exception:
            return timestamp_str


def _to_local_datetime(timestamp_str, *, local_tz=None):
    """Parse timestamp and normalize to local timezone when timezone-aware."""
    if not timestamp_str:
        return None
    try:
        normalized = str(timestamp_str).replace("Z", "+00:00")
        dt = datetime.fromisoformat(normalized)
        if dt.tzinfo is not None:
            return dt.astimezone(local_tz)
        return dt
    except Exception:
        return None


def _display_project_name(project_name):
    """Return only the final directory/project component for cleaner UI labels."""
    if not project_name:
        return "unknown"

    normalized = str(project_name).strip().rstrip("/\\")
    if not normalized:
        return "unknown"

    return normalized.replace("\\", "/").split("/")[-1] or "unknown"


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


def rename_session(session_id, custom_name, db_path=DB_PATH):
    if not session_id:
        return {"ok": False, "error": "session_id é obrigatório."}, 400

    normalized = (custom_name or "").strip()
    if len(normalized) > MAX_CUSTOM_NAME_LENGTH:
        return {"ok": False, "error": f"custom_name deve ter no máximo {MAX_CUSTOM_NAME_LENGTH} caracteres."}, 400

    if not db_path.exists():
        return {"ok": False, "error": "Banco de dados não encontrado."}, 404

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        ensure_custom_name_column(conn)
        existing = conn.execute(
            "SELECT session_id FROM sessions WHERE session_id = ?",
            (session_id,),
        ).fetchone()
        if existing is None:
            return {"ok": False, "error": "Sessão não encontrada."}, 404

        value = normalized if normalized else None
        conn.execute(
            "UPDATE sessions SET custom_name = ? WHERE session_id = ?",
            (value, session_id),
        )
        conn.commit()
        return {
            "ok": True,
            "session_id": session_id,
            "custom_name": value,
        }, 200
    except sqlite3.Error as e:
        return {"ok": False, "error": f"Erro ao renomear sessão: {e}"}, 500
    finally:
        conn.close()


def _parse_usage_percent(value):
    if value is None:
        return None
    try:
        cleaned = str(value).strip().replace("%", "").replace(",", ".")
        if cleaned == "":
            return None
        return float(cleaned)
    except Exception:
        return None


def _parse_usage_tokens(value):
    if value is None:
        return None
    try:
        cleaned = str(value).strip().lower()
        cleaned = cleaned.replace("tokens", "").replace("token", "")
        cleaned = cleaned.replace(",", "").replace("_", "").strip()
        if cleaned == "":
            return None
        return int(float(cleaned))
    except Exception:
        return None


def _extract_usage_block(payload, key):
    block = payload.get(key, {}) or {}
    return {
        "used_percent": _parse_usage_percent(block.get("used_percent")),
        "available_percent": _parse_usage_percent(block.get("available_percent")),
        "used_tokens": _parse_usage_tokens(
            block.get("used_tokens", block.get("used_token_count"))
        ),
        "available_tokens": _parse_usage_tokens(
            block.get("available_tokens", block.get("remaining_tokens"))
        ),
        "limit_tokens": _parse_usage_tokens(
            block.get("limit_tokens", block.get("token_limit"))
        ),
        "resets_at": str(block.get("resets_at") or ""),
    }


def _parse_usage_text(stdout):
    text = (stdout or "").strip()
    session_used = session_avail = week_used = week_avail = None
    session_resets = week_resets = ""

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for line in lines:
        lower = line.lower()
        if "session" in lower:
            used_match = re.search(r"used[^0-9]*([0-9]+(?:[.,][0-9]+)?)\s*%", lower)
            avail_match = re.search(r"(available|left|remaining)[^0-9]*([0-9]+(?:[.,][0-9]+)?)\s*%", lower)
            reset_match = re.search(r"(reset[s]? at|resets?)[^0-9a-z]*([^\n]+)$", line, re.IGNORECASE)
            if used_match:
                session_used = _parse_usage_percent(used_match.group(1))
            if avail_match:
                session_avail = _parse_usage_percent(avail_match.group(2))
            if reset_match:
                session_resets = reset_match.group(2).strip()
        if "week" in lower:
            used_match = re.search(r"used[^0-9]*([0-9]+(?:[.,][0-9]+)?)\s*%", lower)
            avail_match = re.search(r"(available|left|remaining)[^0-9]*([0-9]+(?:[.,][0-9]+)?)\s*%", lower)
            reset_match = re.search(r"(reset[s]? at|resets?)[^0-9a-z]*([^\n]+)$", line, re.IGNORECASE)
            if used_match:
                week_used = _parse_usage_percent(used_match.group(1))
            if avail_match:
                week_avail = _parse_usage_percent(avail_match.group(2))
            if reset_match:
                week_resets = reset_match.group(2).strip()

    return {
        "current_session": {
            "used_percent": session_used,
            "available_percent": session_avail,
            "used_tokens": None,
            "available_tokens": None,
            "limit_tokens": None,
            "resets_at": session_resets,
        },
        "current_week": {
            "used_percent": week_used,
            "available_percent": week_avail,
            "used_tokens": None,
            "available_tokens": None,
            "limit_tokens": None,
            "resets_at": week_resets,
        },
    }


def get_usage_snapshot(timeout_seconds=8):
    commands = [
        ["claude", "/usage", "--json"],
        ["claude", "/usage"],
    ]
    errors = []
    last_excerpt = ""

    for cmd in commands:
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                stdin=subprocess.DEVNULL,
            )
            stdout = (proc.stdout or "").strip()
            stderr = (proc.stderr or "").strip()
            if stdout:
                last_excerpt = stdout[:4000]
            if proc.returncode != 0:
                errors.append(f"{' '.join(cmd)} retornou código {proc.returncode}: {stderr or 'sem stderr'}")
                continue

            # Try JSON output first
            try:
                payload = json.loads(stdout)
                if isinstance(payload, dict):
                    return {
                        "ok": True,
                        "captured_at": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
                        "current_session": _extract_usage_block(payload, "current_session"),
                        "current_week": _extract_usage_block(payload, "current_week"),
                        "raw_excerpt": stdout[:2000],
                        "error": "",
                    }
            except Exception:
                pass

            parsed = _parse_usage_text(stdout)
            return {
                "ok": True,
                "captured_at": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
                "current_session": parsed["current_session"],
                "current_week": parsed["current_week"],
                "raw_excerpt": stdout[:2000],
                "error": "",
            }
        except subprocess.TimeoutExpired:
            errors.append(f"{' '.join(cmd)} expirou após {timeout_seconds}s")
        except FileNotFoundError:
            errors.append("Comando `claude` não encontrado no PATH.")
            break
        except Exception as exc:
            errors.append(f"{' '.join(cmd)} falhou: {exc}")

    return {
        "ok": False,
        "captured_at": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        "current_session": {
            "used_percent": None,
            "available_percent": None,
            "used_tokens": None,
            "available_tokens": None,
            "limit_tokens": None,
            "resets_at": "",
        },
        "current_week": {
            "used_percent": None,
            "available_percent": None,
            "used_tokens": None,
            "available_tokens": None,
            "limit_tokens": None,
            "resets_at": "",
        },
        "raw_excerpt": last_excerpt[:2000],
        "error": "Falha ao capturar saída do Claude CLI. " + " | ".join(errors[:3]),
    }


def get_dashboard_data(db_path=DB_PATH, local_tz=None):
    if not db_path.exists():
        return {"error": "Banco de dados não encontrado. Execute: python cli.py scan"}

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    ensure_custom_name_column(conn)
    ensure_has_tool_marker_column(conn)

    # ── All models (for filter UI) ────────────────────────────────────────────
    model_rows = conn.execute("""
        SELECT COALESCE(model, 'unknown') as model
        FROM turns
        GROUP BY model
        ORDER BY SUM(input_tokens + output_tokens) DESC
    """).fetchall()
    all_models = [r["model"] for r in model_rows]

    turns_rows = conn.execute("""
        SELECT
            timestamp,
            COALESCE(model, 'unknown') as model,
            input_tokens,
            output_tokens,
            cache_read_tokens,
            cache_creation_tokens,
            COALESCE(has_tool_marker, 0) as has_tool_marker
        FROM turns
    """).fetchall()

    daily_acc = defaultdict(lambda: {"input": 0, "output": 0, "cache_read": 0, "cache_creation": 0, "turns": 0})
    hourly_acc = defaultdict(lambda: {"input": 0, "output": 0, "cache_read": 0, "cache_creation": 0, "turns": 0})

    for row in turns_rows:
        local_dt = _to_local_datetime(row["timestamp"], local_tz=local_tz)
        if local_dt is None:
            continue
        day = local_dt.strftime("%Y-%m-%d")
        hour = local_dt.strftime("%H")
        model = row["model"] or "unknown"

        daily = daily_acc[(day, model)]
        daily["input"] += row["input_tokens"] or 0
        daily["output"] += row["output_tokens"] or 0
        daily["cache_read"] += row["cache_read_tokens"] or 0
        daily["cache_creation"] += row["cache_creation_tokens"] or 0
        daily["turns"] += 1

        if (row["has_tool_marker"] or 0) == 0:
            hourly = hourly_acc[(day, hour, model)]
            hourly["input"] += row["input_tokens"] or 0
            hourly["output"] += row["output_tokens"] or 0
            hourly["cache_read"] += row["cache_read_tokens"] or 0
            hourly["cache_creation"] += row["cache_creation_tokens"] or 0
            hourly["turns"] += 1

    daily_by_model = [{
        "day": day,
        "model": model,
        "input": vals["input"],
        "output": vals["output"],
        "cache_read": vals["cache_read"],
        "cache_creation": vals["cache_creation"],
        "turns": vals["turns"],
    } for (day, model), vals in sorted(daily_acc.items())]

    hourly_by_model = [{
        "day": day,
        "hour": hour,
        "model": model,
        "input": vals["input"],
        "output": vals["output"],
        "cache_read": vals["cache_read"],
        "cache_creation": vals["cache_creation"],
        "turns": vals["turns"],
    } for (day, hour, model), vals in sorted(hourly_acc.items())]

    # ── All sessions (client filters by range and model) ──────────────────────
    session_rows = conn.execute("""
        SELECT
            session_id, project_name, first_timestamp, last_timestamp,
            total_input_tokens, total_output_tokens,
            total_cache_read, total_cache_creation, model, turn_count, custom_name
        FROM sessions
        ORDER BY last_timestamp DESC
    """).fetchall()

    sessions_all = []
    for r in session_rows:
        try:
            t1 = datetime.fromisoformat(r["first_timestamp"].replace("Z", "+00:00"))
            t2 = datetime.fromisoformat(r["last_timestamp"].replace("Z", "+00:00"))
            duration_min = round((t2 - t1).total_seconds() / 60, 1)
        except Exception:
            duration_min = 0
        sessions_all.append({
            "session_id":    r["session_id"][:8],
            "session_id_full": r["session_id"],
            "project":       _display_project_name(r["project_name"]),
            "custom_name":   r["custom_name"] or "",
            "last":          _format_timestamp(r["last_timestamp"] or ""),
            "last_date":     (r["last_timestamp"] or "")[:10],
            "last_iso":      r["last_timestamp"] or "",
            "duration_min":  duration_min,
            "model":         r["model"] or "unknown",
            "turns":         r["turn_count"] or 0,
            "input":         r["total_input_tokens"] or 0,
            "output":        r["total_output_tokens"] or 0,
            "cache_read":    r["total_cache_read"] or 0,
            "cache_creation": r["total_cache_creation"] or 0,
        })

    conn.close()

    return {
        "all_models":     all_models,
        "daily_by_model": daily_by_model,
        "hourly_by_model": hourly_by_model,
        "sessions_all":   sessions_all,
        "generated_at":   datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
    }


def get_sessions_for_hour(hour, cutoff=None, cutoff_ts=None, models=None, db_path=DB_PATH, local_tz=None):
    if not db_path.exists():
        return {"error": "Banco de dados não encontrado."}
    if hour is None or len(str(hour)) != 2 or not str(hour).isdigit():
        return {"error": "Hora inválida."}

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    ensure_has_tool_marker_column(conn)
    try:
        model_filter = {m for m in (models or []) if m}
        cutoff_dt = _to_local_datetime(cutoff_ts, local_tz=local_tz) if cutoff_ts else None

        rows = conn.execute("""
            SELECT
                t.session_id as session_id,
                t.timestamp as timestamp,
                COALESCE(t.model, 'unknown') as turn_model,
                t.input_tokens as input_tokens,
                t.output_tokens as output_tokens,
                COALESCE(t.has_tool_marker, 0) as has_tool_marker,
                COALESCE(s.custom_name, '') as custom_name,
                COALESCE(s.project_name, 'unknown') as project_name,
                COALESCE(s.model, COALESCE(t.model, 'unknown')) as session_model
            FROM turns t
            LEFT JOIN sessions s ON s.session_id = t.session_id
        """).fetchall()

        session_acc = {}
        for r in rows:
            if (r["has_tool_marker"] or 0) != 0:
                continue

            local_dt = _to_local_datetime(r["timestamp"], local_tz=local_tz)
            if local_dt is None:
                continue

            if local_dt.strftime("%H") != hour:
                continue
            if cutoff and local_dt.strftime("%Y-%m-%d") < cutoff:
                continue
            if cutoff_dt and local_dt < cutoff_dt:
                continue
            if model_filter and (r["turn_model"] or "unknown") not in model_filter:
                continue

            sid = r["session_id"] or ""
            item = session_acc.get(sid)
            if item is None:
                item = {
                    "session_id_full": sid,
                    "session_id": sid[:8],
                    "custom_name": r["custom_name"] or "",
                    "project": _display_project_name(r["project_name"]),
                    "model": r["session_model"] or "unknown",
                    "last_ts": r["timestamp"] or "",
                    "turns_at_hour": 0,
                    "input": 0,
                    "output": 0,
                }
                session_acc[sid] = item
            if (r["timestamp"] or "") > item["last_ts"]:
                item["last_ts"] = r["timestamp"] or ""
            item["turns_at_hour"] += 1
            item["input"] += r["input_tokens"] or 0
            item["output"] += r["output_tokens"] or 0

        sessions = sorted(session_acc.values(), key=lambda it: it["last_ts"], reverse=True)
        sessions = [{
            "session_id_full": s["session_id_full"],
            "session_id": s["session_id"],
            "custom_name": s["custom_name"],
            "project": s["project"],
            "model": s["model"],
            "last": _format_timestamp(s["last_ts"], local_tz=local_tz),
            "turns_at_hour": s["turns_at_hour"],
            "input": s["input"],
            "output": s["output"],
        } for s in sessions]

        return {
            "hour": hour,
            "cutoff": cutoff or "",
            "cutoff_ts": cutoff_ts or "",
            "models": sorted(model_filter),
            "sessions": sessions,
            "generated_at": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        }
    finally:
        conn.close()

def _extract_text_parts(content):
    if content is None:
        return []
    if isinstance(content, str):
        return [content]
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
                continue
            if not isinstance(item, dict):
                continue
            item_type = item.get("type")
            if item_type == "text" and item.get("text"):
                parts.append(str(item["text"]))
            elif item_type == "tool_use":
                parts.append(f"[tool_use] {item.get('name') or 'unknown'}")
            elif item_type == "tool_result":
                nested = _extract_text_parts(item.get("content"))
                if nested:
                    parts.append("[tool_result]\n" + "\n".join(nested))
            elif item.get("text"):
                parts.append(str(item["text"]))
        return parts
    if isinstance(content, dict):
        nested = content.get("content")
        if nested is not None:
            return _extract_text_parts(nested)
        if content.get("text") is not None:
            return [str(content.get("text"))]
    return [str(content)]


def _extract_message_text(record):
    message = record.get("message", {})
    if not isinstance(message, dict):
        return ""
    parts = _extract_text_parts(message.get("content"))
    if not parts and message.get("text") is not None:
        parts = [str(message.get("text"))]
    return "\n\n".join(p for p in parts if p).strip()


def find_transcript_path_for_session(session_id, db_path=DB_PATH):
    if not db_path.exists():
        return None

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute("""
            SELECT path
            FROM processed_files
            ORDER BY mtime DESC
        """).fetchall()
    except sqlite3.OperationalError:
        rows = []
    finally:
        conn.close()

    for row in rows:
        filepath = Path(row["path"])
        if not filepath.exists():
            continue
        try:
            with open(filepath, encoding="utf-8", errors="replace") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if record.get("sessionId") == session_id:
                        return filepath
        except OSError:
            continue

    return None


def get_session_history(session_id, db_path=DB_PATH):
    if not session_id:
        return {"error": "É necessário informar um ID de sessão."}

    transcript_path = find_transcript_path_for_session(session_id, db_path=db_path)
    if not transcript_path:
        return {"error": "Transcrição da sessão não encontrada."}

    entries = []
    message_index = {}

    try:
        with open(transcript_path, encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue

                if record.get("sessionId") != session_id:
                    continue

                role = record.get("type")
                if role not in ("user", "assistant"):
                    continue

                timestamp = _format_timestamp(record.get("timestamp") or "")
                text = _extract_message_text(record) or "(sem conteúdo de texto)"
                message = record.get("message", {})
                message_id = message.get("id") if isinstance(message, dict) else None
                entry = {
                    "role": role,
                    "timestamp": timestamp,
                    "text": text,
                }

                if message_id:
                    if message_id in message_index:
                        entries[message_index[message_id]] = entry
                    else:
                        message_index[message_id] = len(entries)
                        entries.append(entry)
                else:
                    entries.append(entry)
    except OSError as e:
        return {"error": f"Não foi possível ler a transcrição da sessão: {e}"}

    if not entries:
        return {"error": "Nenhuma mensagem foi encontrada para esta sessão."}

    custom_name = ""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        ensure_custom_name_column(conn)
        row = conn.execute(
            "SELECT custom_name FROM sessions WHERE session_id = ?",
            (session_id,),
        ).fetchone()
        if row and row["custom_name"]:
            custom_name = row["custom_name"]
    except sqlite3.Error:
        custom_name = ""
    finally:
        conn.close()

    return {
        "session_id": session_id,
        "custom_name": custom_name,
        "transcript_path": str(transcript_path),
        "entries": entries,
    }


def render_session_history_html(session_data):
    header_html = render_app_header(
        "Histórico da Sessão",
        subtitle="Visualização detalhada de uma sessão",
        show_back_link=False,
        right_html=HEADER_THEME_TOGGLE_HTML,
    )
    footer_html = render_app_footer()
    if "error" in session_data:
        err = escape(session_data["error"])
        return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<link rel="icon" type="image/svg+xml" href="/images/favicon.svg">
<title>ClaudeFlow - Sessão</title>
<style>
  :root, [data-theme="dark"] {{
    --bg: #0f1117;
    --card: #1a1d27;
    --border: #2a2d3a;
    --text: #e2e8f0;
    --muted: #8892a4;
    --accent: #d97757;
    --link: #6aa6ff;
    --toggle-bg: #1f2330;
    --toggle-text: #dbe6ff;
  }}
  [data-theme="light"] {{
    --bg: #f5f7fb;
    --card: #ffffff;
    --border: #d6deea;
    --text: #0f172a;
    --muted: #475569;
    --accent: #c55f3c;
    --link: #1d4ed8;
    --toggle-bg: #eef2ff;
    --toggle-text: #1e293b;
  }}
  * {{ box-sizing: border-box; }}
{COMMON_LAYOUT_STYLES}
  body {{ background: var(--bg); color: var(--text); font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; margin: 0; }}
  .wrap {{ max-width: 960px; margin: 0 auto; padding: 24px; }}
  h1 {{ font-size: 20px; margin-bottom: 12px; color: var(--accent); }}
  p {{ color: var(--muted); }}
  a {{ color: var(--link); text-decoration: none; }}
  a:hover {{ text-decoration: underline; }}
</style>
</head>
<body>
{header_html}
<div class="wrap">
  <h1>Histórico da Sessão</h1>
  <p>{err}</p>
</div>
{footer_html}
</body>
</html>"""

    rows = []
    for entry in session_data["entries"]:
        role = escape(entry["role"])
        role_label = "Usuário" if role == "user" else "Assistente"
        timestamp = escape(entry["timestamp"] or "-")
        raw_text = entry["text"] or ""
        text = escape(raw_text)
        tool_marker_class = " tool-message" if "[tool_" in raw_text.lower() else ""
        row_html = f"""<article class="entry {role}{tool_marker_class}">
  <div class="entry-meta">
    <span class="role">{role_label}</span>
    <span class="time">{timestamp}</span>
  </div>
  <pre>{text}</pre>
</article>"""
        rows.append(row_html)

    sid_raw = session_data["session_id"]
    sid = escape(sid_raw)
    custom_name_raw = (session_data.get("custom_name") or "").strip()
    custom_name = escape(custom_name_raw)
    source = escape(session_data["transcript_path"])
    content = "\n".join(rows)
    title_text = custom_name if custom_name_raw else sid_raw
    custom_name_meta = f"<div class=\"meta\">ID da sessão: {sid}</div>" if custom_name_raw else ""
    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<link rel="icon" type="image/svg+xml" href="/images/favicon.svg">
<title>{escape(f"ClaudeFlow - {title_text}")}</title>
<style>
  :root, [data-theme="dark"] {{
    --bg: #0f1117;
    --card: #1a1d27;
    --border: #2a2d3a;
    --text: #e2e8f0;
    --muted: #8892a4;
    --accent: #d97757;
    --link: #6aa6ff;
    --entry-user-bg: #12243f;
    --entry-assistant-bg: #113126;
    --entry-user-text: #8fc2ff;
    --entry-assistant-text: #8ce8b7;
    --toggle-bg: #1f2330;
    --toggle-text: #dbe6ff;
  }}
  [data-theme="light"] {{
    --bg: #f5f7fb;
    --card: #ffffff;
    --border: #d6deea;
    --text: #0f172a;
    --muted: #475569;
    --accent: #c55f3c;
    --link: #1d4ed8;
    --entry-user-bg: #dbeafe;
    --entry-assistant-bg: #dcfce7;
    --entry-user-text: #1d4ed8;
    --entry-assistant-text: #047857;
    --toggle-bg: #eef2ff;
    --toggle-text: #1e293b;
  }}
  * {{ box-sizing: border-box; }}
{COMMON_LAYOUT_STYLES}
  body {{ margin: 0; background: var(--bg); color: var(--text); font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; }}
  .wrap {{ width: min(1100px, 100%); margin: 0 auto; padding: clamp(16px, 3vw, 28px); }}
  .panel {{ background: var(--card); border: 1px solid var(--border); border-radius: 14px; padding: clamp(14px, 2.4vw, 24px); }}
  .topbar {{ display: flex; justify-content: flex-start; gap: 10px; align-items: center; margin-bottom: 16px; flex-wrap: wrap; }}
  .hide-tools {{ display: inline-flex; align-items: center; gap: 8px; color: var(--muted); font-size: 13px; }}
  .hide-tools label {{ display: inline-flex; align-items: center; gap: 6px; cursor: pointer; user-select: none; }}
  .hide-tools input {{ width: 14px; height: 14px; accent-color: var(--link); cursor: pointer; }}
  .tooltip {{
    position: relative;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 18px;
    height: 18px;
    border-radius: 50%;
    border: 1px solid var(--border);
    color: var(--muted);
    font-size: 12px;
    cursor: help;
  }}
  .tooltip-text {{
    position: absolute;
    top: calc(100% + 8px);
    right: 0;
    width: min(320px, 70vw);
    padding: 8px 10px;
    border-radius: 8px;
    border: 1px solid var(--border);
    background: var(--card);
    color: var(--text);
    line-height: 1.35;
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.2);
    opacity: 0;
    pointer-events: none;
    transform: translateY(-4px);
    transition: opacity .18s ease, transform .18s ease;
    z-index: 20;
  }}
  .tooltip:hover .tooltip-text, .tooltip:focus-within .tooltip-text {{
    opacity: 1;
    transform: translateY(0);
  }}
  h1 {{ margin: 0 0 8px; font-size: 20px; color: var(--accent); }}
  .meta {{ color: var(--muted); font-size: 12px; margin-bottom: 16px; word-break: break-all; }}
  .session-title-row {{ display: flex; align-items: center; gap: 10px; flex-wrap: wrap; margin-bottom: 8px; }}
  .session-edit-btn {{ border: 1px solid var(--border); background: transparent; color: var(--muted); border-radius: 6px; padding: 4px 10px; cursor: pointer; font-size: 12px; }}
  .session-edit-btn:hover {{ color: var(--text); border-color: var(--accent); }}
  .session-edit-btn:disabled {{ opacity: 0.6; cursor: wait; }}
  #theme-toggle-button {{
    position: relative;
    display: flex;
    align-items: center;
    width: 59px;
    height: 35px;
    cursor: pointer;
  }}
  #theme-toggle-button svg {{ display: block; }}
  #toggle {{
    opacity: 0;
    width: 0;
    height: 0;
  }}
  #container, #patches, #stars, #button, #sun, #moon, #cloud {{
    transition-property: all;
    transition-timing-function: cubic-bezier(0.4, 0, 0.2, 1);
    transition-duration: 0.25s;
  }}
  #toggle:checked + svg #container {{ fill: #2b4360; }}
  #toggle:checked + svg #button {{ transform: translate(28px, 2.333px); }}
  #sun {{ opacity: 1; }}
  #toggle:checked + svg #sun {{ opacity: 0; }}
  #moon {{ opacity: 0; }}
  #toggle:checked + svg #moon {{ opacity: 1; }}
  #cloud {{ opacity: 1; }}
  #toggle:checked + svg #cloud {{ opacity: 0; }}
  #stars {{ opacity: 0; }}
  #toggle:checked + svg #stars {{ opacity: 1; }}
  .entry {{ background: var(--card); border: 1px solid var(--border); border-radius: 8px; padding: 12px; margin-bottom: 12px; }}
  .entry-meta {{ display: flex; justify-content: space-between; gap: 12px; margin-bottom: 10px; font-size: 12px; color: var(--muted); }}
  .entry .role {{ font-weight: 700; border-radius: 999px; padding: 2px 8px; display: inline-block; }}
  .entry.user .role {{ color: var(--entry-user-text); background: var(--entry-user-bg); }}
  .entry.assistant .role {{ color: var(--entry-assistant-text); background: var(--entry-assistant-bg); }}
  .entry pre {{ margin: 0; white-space: pre-wrap; word-break: break-word; font-family: inherit; line-height: 1.45; }}
  body.hide-tools-enabled .entry.tool-message {{ display: none; }}
</style>
</head>
<body>
{header_html}
<div class="wrap">
  <div class="panel">
  <div class="topbar">
    <div class="hide-tools">
      <label for="hide-tools-toggle">
        <input type="checkbox" id="hide-tools-toggle">
        <span>Ocultar tools</span>
      </label>
      <span class="tooltip" tabindex="0" aria-label="Ajuda sobre ocultar tools">
        ?
        <span class="tooltip-text">Oculta mensagens que contenham [tool_*], reduzindo poluição visual e facilitando a leitura da sessão.</span>
      </span>
    </div>
  </div>
  <div class="session-title-row">
    <h1 id="session-title">{custom_name if custom_name_raw else f"Sessão {sid}"}</h1>
    <button id="session-rename-btn" class="session-edit-btn" type="button">✏️ Editar nome</button>
  </div>
  {custom_name_meta}
  <div class="meta">Origem: {source}</div>
  {content}
  </div>
</div>
{footer_html}
<script>
  const MAX_CUSTOM_NAME_LENGTH = 80;
  const sessionId = {json.dumps(sid_raw)};
  let currentCustomName = {json.dumps(custom_name_raw)};
  const THEME_STORAGE_KEY = 'claude_usage_theme';
  const HIDE_TOOLS_STORAGE_KEY = 'claude_usage_hide_tools';
  function getPreferredTheme() {{
    const saved = localStorage.getItem(THEME_STORAGE_KEY);
    if (saved === 'dark' || saved === 'light') return saved;
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  }}
  function applyTheme(theme) {{
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem(THEME_STORAGE_KEY, theme);
    const toggle = document.getElementById('toggle');
    if (toggle) toggle.checked = theme === 'dark';
  }}
  applyTheme(getPreferredTheme());
  document.getElementById('toggle')?.addEventListener('change', (event) => {{
    applyTheme(event.target.checked ? 'dark' : 'light');
  }});
  function applyHideTools(enabled) {{
    document.body.classList.toggle('hide-tools-enabled', enabled);
    const hideToolsToggle = document.getElementById('hide-tools-toggle');
    if (hideToolsToggle) hideToolsToggle.checked = enabled;
    localStorage.setItem(HIDE_TOOLS_STORAGE_KEY, enabled ? '1' : '0');
  }}
  applyHideTools(localStorage.getItem(HIDE_TOOLS_STORAGE_KEY) === '1');
  document.getElementById('hide-tools-toggle')?.addEventListener('change', (event) => {{
    applyHideTools(Boolean(event.target.checked));
  }});
  async function renameCurrentSession() {{
    const titleEl = document.getElementById('session-title');
    const btn = document.getElementById('session-rename-btn');
    if (!titleEl || !btn) return;
    const newName = window.prompt('Digite o nome personalizado da sessão (vazio para remover):', currentCustomName);
    if (newName === null) return;
    if (newName.length > MAX_CUSTOM_NAME_LENGTH) {{
      window.alert(`Nome muito longo (máximo ${{MAX_CUSTOM_NAME_LENGTH}} caracteres).`);
      return;
    }}
    btn.disabled = true;
    btn.textContent = 'Salvando...';
    try {{
      const resp = await fetch('/api/session/rename', {{
        method: 'POST',
        headers: {{ 'Content-Type': 'application/json' }},
        body: JSON.stringify({{
          session_id: sessionId,
          custom_name: newName,
        }}),
      }});
      const data = await resp.json();
      if (!resp.ok || !data.ok) {{
        throw new Error(data.error || 'Falha ao renomear sessão.');
      }}
      const newTitle = (data.custom_name || '').trim() || sessionId;
      currentCustomName = (data.custom_name || '').trim();
      titleEl.textContent = currentCustomName || ('Sessão ' + sessionId.slice(0, 8));
      document.title = 'ClaudeFlow - ' + newTitle;
    }} catch (error) {{
      window.alert(error.message || 'Erro ao salvar nome.');
    }} finally {{
      btn.disabled = false;
      btn.textContent = '✏️ Editar nome';
    }}
  }}
  document.getElementById('session-rename-btn')?.addEventListener('click', renameCurrentSession);
</script>
</body>
</html>"""


def render_hour_sessions_html(data):
    footer_html = render_app_footer()
    if "error" in data:
        err = escape(data["error"])
        header_html = render_app_header(
            "Sessões por Hora",
            subtitle="Resumo por faixa horária",
            show_back_link=False,
            right_html=HEADER_THEME_TOGGLE_HTML,
        )
        return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>ClaudeFlow - Sessões por Hora</title>
  <style>
    :root, [data-theme="dark"] {{
      --bg: #0f1117;
      --card: #1a1d27;
      --border: #2a2d3a;
      --text: #e2e8f0;
      --muted: #94a3b8;
      --link: #6aa6ff;
    }}
    [data-theme="light"] {{
      --bg: #f8fafc;
      --card: #ffffff;
      --border: #e2e8f0;
      --text: #0f172a;
      --muted: #64748b;
      --link: #2563eb;
    }}
{COMMON_LAYOUT_STYLES}
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; margin: 0; background:var(--bg); color:var(--text); }}
    .wrap {{ max-width: 1100px; margin: 0 auto; padding: 24px; }}
    a {{ color:var(--link); text-decoration:none; }}
    a:hover {{ text-decoration:underline; }}
    #theme-toggle-button {{
      position: relative;
      display: flex;
      align-items: center;
      width: 59px;
      height: 35px;
      cursor: pointer;
    }}
    #theme-toggle-button svg {{ display: block; }}
    #toggle {{
      opacity: 0;
      width: 0;
      height: 0;
    }}
    #container, #patches, #stars, #button, #sun, #moon, #cloud {{
      transition-property: all;
      transition-timing-function: cubic-bezier(0.4, 0, 0.2, 1);
      transition-duration: 0.25s;
    }}
    #toggle:checked + svg #container {{ fill: #2b4360; }}
    #toggle:checked + svg #button {{ transform: translate(28px, 2.333px); }}
    #sun {{ opacity: 1; }}
    #toggle:checked + svg #sun {{ opacity: 0; }}
    #moon {{ opacity: 0; }}
    #toggle:checked + svg #moon {{ opacity: 1; }}
    #cloud {{ opacity: 1; }}
    #toggle:checked + svg #cloud {{ opacity: 0; }}
    #stars {{ opacity: 0; }}
    #toggle:checked + svg #stars {{ opacity: 1; }}
  </style>
</head>
<body>{header_html}<div class="wrap"><h1>Sessões por Hora</h1><p>{err}</p></div>{footer_html}
<script>
  const THEME_STORAGE_KEY = 'claude_usage_theme';
  function getPreferredTheme() {{
    const saved = localStorage.getItem(THEME_STORAGE_KEY);
    if (saved === 'dark' || saved === 'light') return saved;
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  }}
  function applyTheme(theme) {{
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem(THEME_STORAGE_KEY, theme);
    const toggle = document.getElementById('toggle');
    if (toggle) toggle.checked = theme === 'dark';
  }}
  applyTheme(getPreferredTheme());
  document.getElementById('toggle')?.addEventListener('change', (event) => {{
    applyTheme(event.target.checked ? 'dark' : 'light');
  }});
</script>
</body>
</html>"""

    hour = escape(f"{data.get('hour', '00')}:00")
    cutoff = escape(data.get("cutoff") or "início")
    cutoff_ts = (data.get("cutoff_ts") or "").strip()
    if cutoff_ts:
        cutoff = escape(_format_timestamp(cutoff_ts))
    models = data.get("models") or []
    models_text = ", ".join(escape(m) for m in models) if models else "todos"
    header_html = render_app_header(
        f"Sessões no horário {hour}",
        subtitle=f"Período: {cutoff} · Modelos: {models_text}",
        show_back_link=False,
        right_html=HEADER_THEME_TOGGLE_HTML,
    )
    rows = []
    for s in data.get("sessions", []):
        sid = escape(s["session_id"])
        sid_full = escape(s["session_id_full"])
        custom = escape(s["custom_name"] or "")
        project = escape(s["project"])
        model = escape(s["model"])
        last = escape(s["last"])
        turns_at_hour = int(s["turns_at_hour"] or 0)
        input_tokens = int(s["input"] or 0)
        output_tokens = int(s["output"] or 0)
        label = custom if custom else sid
        rows.append(
            f"<tr>"
            f"<td><a href=\"/session/{sid_full}\">{label}</a></td>"
            f"<td>{project}</td>"
            f"<td>{model}</td>"
            f"<td>{turns_at_hour}</td>"
            f"<td>{input_tokens:,}</td>"
            f"<td>{output_tokens:,}</td>"
            f"<td>{last}</td>"
            f"</tr>"
        )
    table_rows = "\n".join(rows) if rows else "<tr><td colspan=\"7\">Nenhuma sessão encontrada para esse horário e filtros.</td></tr>"
    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>ClaudeFlow - Sessões por Hora ({hour})</title>
  <style>
    :root, [data-theme="dark"] {{
      --bg: #0f1117;
      --card: #1a1d27;
      --border: #2a2d3a;
      --text: #e2e8f0;
      --muted: #94a3b8;
      --link: #6aa6ff;
    }}
    [data-theme="light"] {{
      --bg: #f8fafc;
      --card: #ffffff;
      --border: #e2e8f0;
      --text: #0f172a;
      --muted: #64748b;
      --link: #2563eb;
    }}
{COMMON_LAYOUT_STYLES}
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; margin: 0; background:var(--bg); color:var(--text); }}
    .wrap {{ max-width: 1200px; margin: 0 auto; padding: 24px; }}
    .meta {{ color:var(--muted); margin-bottom: 12px; }}
    a {{ color:var(--link); text-decoration:none; }}
    a:hover {{ text-decoration:underline; }}
    table {{ width:100%; border-collapse:collapse; }}
    th, td {{ border-bottom:1px solid var(--border); padding:10px 12px; text-align:left; }}
    th {{ color:var(--muted); font-size:12px; text-transform:uppercase; letter-spacing:.04em; }}
    #theme-toggle-button {{
      position: relative;
      display: flex;
      align-items: center;
      width: 59px;
      height: 35px;
      cursor: pointer;
    }}
    #theme-toggle-button svg {{ display: block; }}
    #toggle {{
      opacity: 0;
      width: 0;
      height: 0;
    }}
    #container, #patches, #stars, #button, #sun, #moon, #cloud {{
      transition-property: all;
      transition-timing-function: cubic-bezier(0.4, 0, 0.2, 1);
      transition-duration: 0.25s;
    }}
    #toggle:checked + svg #container {{ fill: #2b4360; }}
    #toggle:checked + svg #button {{ transform: translate(28px, 2.333px); }}
    #sun {{ opacity: 1; }}
    #toggle:checked + svg #sun {{ opacity: 0; }}
    #moon {{ opacity: 0; }}
    #toggle:checked + svg #moon {{ opacity: 1; }}
    #cloud {{ opacity: 1; }}
    #toggle:checked + svg #cloud {{ opacity: 0; }}
    #stars {{ opacity: 0; }}
    #toggle:checked + svg #stars {{ opacity: 1; }}
  </style>
</head>
<body>
  {header_html}
  <div class="wrap">
    <div class="meta">Atualizado em: {escape(data.get("generated_at") or "")}</div>
    <table>
      <thead>
        <tr>
          <th>Sessão</th>
          <th>Projeto</th>
          <th>Modelo</th>
          <th>Interações no horário</th>
          <th>Entrada</th>
          <th>Saída</th>
          <th>Última atividade</th>
        </tr>
      </thead>
      <tbody>{table_rows}</tbody>
    </table>
  </div>
  {footer_html}
<script>
  const THEME_STORAGE_KEY = 'claude_usage_theme';
  function getPreferredTheme() {{
    const saved = localStorage.getItem(THEME_STORAGE_KEY);
    if (saved === 'dark' || saved === 'light') return saved;
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  }}
  function applyTheme(theme) {{
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem(THEME_STORAGE_KEY, theme);
    const toggle = document.getElementById('toggle');
    if (toggle) toggle.checked = theme === 'dark';
  }}
  applyTheme(getPreferredTheme());
  document.getElementById('toggle')?.addEventListener('change', (event) => {{
    applyTheme(event.target.checked ? 'dark' : 'light');
  }});
</script>
</body>
</html>"""


HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<link rel="icon" type="image/svg+xml" href="/images/favicon.svg">
<title>ClaudeFlow - Dashboard</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
  :root, [data-theme="dark"] {
    --bg: #0f1117;
    --card: #1a1d27;
    --border: #2a2d3a;
    --text: #e2e8f0;
    --muted: #8892a4;
    --accent: #d97757;
    --blue: #4f8ef7;
    --green: #4ade80;
    --hover-bg: rgba(255, 255, 255, 0.04);
    --active-bg: rgba(217, 119, 87, 0.18);
    --tag-bg: rgba(79, 142, 247, 0.20);
    --table-hover-bg: rgba(255, 255, 255, 0.03);
    --chart-grid: #2a2d3a;
    --chart-text: #8892a4;
  }
  :root[data-theme="light"] {
    --bg: #f6f8fc;
    --card: #ffffff;
    --border: #d7dfeb;
    --text: #1f2937;
    --muted: #516073;
    --accent: #c2410c;
    --blue: #1d4ed8;
    --green: #15803d;
    --hover-bg: rgba(15, 23, 42, 0.05);
    --active-bg: rgba(194, 65, 12, 0.15);
    --tag-bg: rgba(29, 78, 216, 0.12);
    --table-hover-bg: rgba(15, 23, 42, 0.04);
    --chart-grid: #d7dfeb;
    --chart-text: #516073;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: var(--bg); color: var(--text); font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; font-size: 14px; }

  header { background: var(--card); border-bottom: 1px solid var(--border); padding: 16px 24px; display: flex; align-items: center; justify-content: space-between; gap: 12px; }
  header h1 { margin: 0; display: flex; align-items: center; }
  .logomarca { display: block; height: 36px; width: auto; max-width: min(320px, 48vw); object-fit: contain; }
  .meta { color: var(--muted); font-size: 12px; }
  .header-controls { display: flex; align-items: center; gap: 8px; margin-left: auto; }
  .header-actions { display: flex; align-items: center; gap: 8px; }
  .refresh-toggle {
    position: relative;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 32px;
    height: 32px;
    border: 1px solid var(--border);
    border-radius: 6px;
    color: var(--muted);
    background: var(--card);
    cursor: pointer;
  }
  .refresh-toggle:hover { border-color: var(--accent); color: var(--text); }
  .refresh-toggle__input {
    position: absolute;
    width: 1px;
    height: 1px;
    opacity: 0;
    pointer-events: none;
  }
  .refresh-toggle__icon {
    width: 15px;
    height: 15px;
    fill: currentColor;
  }
  .refresh-toggle__icon--play { display: none; }
  .refresh-toggle__input:not(:checked) ~ .refresh-toggle__icon--play { display: block; }
  .refresh-toggle__input:not(:checked) ~ .refresh-toggle__icon--pause { display: none; }
  #theme-toggle-button {
    /* font-size: 17px; */
    position: relative;
    display: flex;
    align-items: center;
    width: 59px;
    height: 35px;
    cursor: pointer;
  }
  #theme-toggle-button svg { display: block; }
  #toggle {
    opacity: 0;
    width: 0;
    height: 0;
  }
  #container, #patches, #stars, #button, #sun, #moon, #cloud {
    transition-property: all;
    transition-timing-function: cubic-bezier(0.4, 0, 0.2, 1);
    transition-duration: 0.25s;
  }
  #toggle:checked + svg #container { fill: #2b4360; }
  #toggle:checked + svg #button { transform: translate(28px, 2.333px); }
  #sun { opacity: 1; }
  #toggle:checked + svg #sun { opacity: 0; }
  #moon { opacity: 0; }
  #toggle:checked + svg #moon { opacity: 1; }
  #cloud { opacity: 1; }
  #toggle:checked + svg #cloud { opacity: 0; }
  #stars { opacity: 0; }
  #toggle:checked + svg #stars { opacity: 1; }
  #rescan-btn { background: var(--card); border: 1px solid var(--border); color: var(--muted); padding: 4px 12px; border-radius: 6px; cursor: pointer; font-size: 12px; margin-top: 0; height: 32px; display: inline-flex; align-items: center; }
  #rescan-btn:hover { color: var(--text); border-color: var(--accent); }
  #rescan-btn:disabled { opacity: 0.5; cursor: not-allowed; }

  #filter-bar { background: var(--card); border-bottom: 1px solid var(--border); padding: 10px 24px; display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
  .filter-label { font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; color: var(--muted); white-space: nowrap; }
  .filter-sep { width: 1px; height: 22px; background: var(--border); flex-shrink: 0; }
  #model-checkboxes { display: flex; flex-wrap: wrap; gap: 6px; }
  .model-cb-label { display: flex; align-items: center; gap: 5px; padding: 3px 10px; border-radius: 20px; border: 1px solid var(--border); cursor: pointer; font-size: 12px; color: var(--muted); transition: border-color 0.15s, color 0.15s, background 0.15s; user-select: none; }
  .model-cb-label:hover { border-color: var(--accent); color: var(--text); }
  .model-cb-label.checked { background: var(--active-bg); border-color: var(--accent); color: var(--text); }
  .model-cb-label input { display: none; }
  .filter-btn { padding: 3px 10px; border-radius: 4px; border: 1px solid var(--border); background: transparent; color: var(--muted); font-size: 11px; cursor: pointer; white-space: nowrap; }
  .filter-btn:hover { border-color: var(--accent); color: var(--text); }
  .range-group { display: flex; border: 1px solid var(--border); border-radius: 6px; overflow: hidden; flex-shrink: 0; }
  .range-btn { padding: 4px 13px; background: transparent; border: none; border-right: 1px solid var(--border); color: var(--muted); font-size: 12px; cursor: pointer; transition: background 0.15s, color 0.15s; }
  .range-btn:last-child { border-right: none; }
  .range-btn:hover { background: var(--hover-bg); color: var(--text); }
  .range-btn.active { background: var(--active-bg); color: var(--accent); font-weight: 600; }

  .container { max-width: 1400px; margin: 0 auto; padding: 24px; }
  .container > .meta { margin-bottom: 12px; }
  .stats-row { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 16px; margin-bottom: 24px; }
  .stat-card { background: var(--card); border: 1px solid var(--border); border-radius: 8px; padding: 16px; }
  .stat-card .label { color: var(--muted); font-size: 11px; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 6px; }
  .stat-card .value { font-size: 22px; font-weight: 700; }
  .stat-card .sub { color: var(--muted); font-size: 11px; margin-top: 4px; }

  .charts-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 24px; }
  .chart-card { background: var(--card); border: 1px solid var(--border); border-radius: 8px; padding: 20px; }
  .chart-card.wide { grid-column: 1 / -1; }
  .chart-card h2 { font-size: 13px; font-weight: 600; color: var(--muted); text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 16px; }
  .chart-title-row { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
  .chart-wrap { position: relative; height: 240px; }
  .chart-wrap.tall { height: 300px; }

  table { width: 100%; border-collapse: collapse; }
  th { text-align: left; padding: 8px 12px; font-size: 11px; text-transform: uppercase; letter-spacing: 0.05em; color: var(--muted); border-bottom: 1px solid var(--border); white-space: nowrap; }
  th.sortable { cursor: pointer; user-select: none; }
  th.sortable:hover { color: var(--text); }
  .th-with-tooltip { display: inline-flex; align-items: center; gap: 6px; }
  .tooltip {
    position: relative;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 16px;
    height: 16px;
    border-radius: 50%;
    border: 1px solid var(--border);
    color: var(--muted);
    font-size: 10px;
    cursor: help;
    line-height: 1;
  }
  .tooltip-text {
    position: absolute;
    top: calc(100% + 8px);
    right: 0;
    width: min(320px, 70vw);
    padding: 8px 10px;
    border-radius: 8px;
    border: 1px solid var(--border);
    background: var(--card);
    color: var(--text);
    line-height: 1.35;
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.2);
    text-transform: none;
    letter-spacing: normal;
    font-weight: 400;
    white-space: normal;
    opacity: 0;
    pointer-events: none;
    transform: translateY(-4px);
    transition: opacity .18s ease, transform .18s ease;
    z-index: 20;
  }
  .tooltip:hover .tooltip-text, .tooltip:focus-within .tooltip-text {
    opacity: 1;
    transform: translateY(0);
  }
  .sort-icon { font-size: 9px; opacity: 0.8; }
  td { padding: 10px 12px; border-bottom: 1px solid var(--border); font-size: 13px; }
  tr:last-child td { border-bottom: none; }
  tr:hover td { background: var(--table-hover-bg); }
  .model-tag { display: inline-block; padding: 2px 7px; border-radius: 4px; font-size: 11px; background: var(--tag-bg); color: var(--blue); }
  .cost { color: var(--green); font-family: monospace; }
  .cost-na { color: var(--muted); font-family: monospace; font-size: 11px; }
  .num { font-family: monospace; }
  .muted { color: var(--muted); }
  .session-link { color: var(--blue); text-decoration: none; }
  .session-link:hover { text-decoration: underline; }
  .rename-btn { border: 1px solid var(--border); background: transparent; color: var(--muted); border-radius: 6px; padding: 2px 8px; cursor: pointer; font-size: 12px; }
  .rename-btn:hover { color: var(--text); border-color: var(--accent); }
  .rename-btn:disabled { opacity: 0.6; cursor: wait; }
  .toast-container { position: fixed; right: 16px; bottom: 16px; display: grid; gap: 8px; z-index: 9999; }
  .toast { padding: 10px 12px; border-radius: 8px; border: 1px solid var(--border); background: var(--card); color: var(--text); font-size: 12px; box-shadow: 0 6px 18px rgba(0,0,0,.25); }
  .toast.success { border-color: #16a34a; }
  .toast.error { border-color: #dc2626; }
  .toast.info { border-color: var(--blue); }
  .section-title { font-size: 13px; font-weight: 600; color: var(--muted); text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 12px; }
  .section-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
  .section-header .section-title { margin-bottom: 0; }
  .export-btn { background: var(--card); border: 1px solid var(--border); color: var(--muted); padding: 3px 10px; border-radius: 5px; cursor: pointer; font-size: 11px; }
  .export-btn:hover { color: var(--text); border-color: var(--accent); }
  .table-footer { display: flex; justify-content: space-between; align-items: center; gap: 10px; margin-top: 12px; color: var(--muted); font-size: 12px; }
  .pager { display: inline-flex; gap: 6px; align-items: center; flex-wrap: wrap; }
  .pager-btn { background: var(--card); border: 1px solid var(--border); color: var(--muted); padding: 4px 8px; border-radius: 6px; cursor: pointer; font-size: 12px; }
  .pager-btn:hover { color: var(--text); border-color: var(--accent); }
  .pager-btn:disabled { opacity: 0.5; cursor: not-allowed; }
  .pager-label { min-width: 100px; text-align: center; }
  .table-card { background: var(--card); border: 1px solid var(--border); border-radius: 8px; padding: 20px; margin-bottom: 24px; overflow-x: auto; }
  .hourly-list { max-height: 320px; overflow-y: auto; padding-right: 4px; }
  .hourly-meta { color: var(--muted); font-size: 12px; margin-bottom: 8px; line-height: 1.45; }
  .hourly-row { display: grid; grid-template-columns: 70px 1fr 180px; gap: 10px; align-items: center; padding: 5px 0; border-bottom: 1px solid var(--border); font-family: monospace; font-size: 13px; }
  .hourly-row:last-child { border-bottom: none; }
  .hourly-track { height: 8px; border-radius: 999px; background: var(--border); overflow: hidden; }
  .hourly-fill { height: 100%; background: linear-gradient(90deg, #4f8ef7, #4ade80); }
  .insights-card { background: var(--card); border: 1px solid var(--border); border-radius: 8px; padding: 20px; margin-bottom: 24px; }
  .usage-panel { background: var(--card); border: 1px solid var(--border); border-radius: 8px; padding: 20px; margin-bottom: 24px; }
  .usage-panel-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 12px; }
  .usage-box { border: 1px solid var(--border); border-radius: 8px; padding: 12px; background: transparent; }
  .usage-box h3 { font-size: 12px; text-transform: uppercase; letter-spacing: .05em; color: var(--muted); margin-bottom: 8px; }
  .usage-line { font-size: 13px; margin-bottom: 4px; color: var(--text); }
  .usage-line .muted { font-size: 12px; }
  .usage-error { color: #f87171; font-size: 12px; margin-top: 8px; }
  .usage-hint { color: var(--muted); font-size: 12px; margin-top: 10px; }
  .insight-list { margin: 0; padding-left: 18px; display: grid; gap: 10px; }
  .insight-list li { color: var(--text); line-height: 1.5; }
  .insight-list .hint { color: var(--muted); font-size: 12px; }
  .disclaimer-banner {
    margin: 10px 24px;
    padding: 10px 12px;
    border: 1px solid var(--border);
    border-radius: 8px;
    background: var(--card);
    color: var(--muted);
    font-size: 12px;
    line-height: 1.5;
  }
  .disclaimer-banner strong { color: var(--text); }
  .disclaimer-banner p { margin: 0; }
  .disclaimer-banner p + p { margin-top: 8px; }

  footer { border-top: 1px solid var(--border); padding: 20px 24px; margin-top: 8px; }
  .footer-content { max-width: 1400px; margin: 0 auto; text-align: center; }
  .footer-content p { color: var(--muted); font-size: 12px; line-height: 1.7; margin-bottom: 4px; }
  .footer-content p:last-child { margin-bottom: 0; }
  .footer-content a { color: var(--blue); text-decoration: none; }
  .footer-content a:hover { text-decoration: underline; }

  @media (max-width: 768px) { .charts-grid { grid-template-columns: 1fr; } .chart-card.wide { grid-column: 1; } }
</style>
</head>
<body>
<header>
  <h1><img class="logomarca" src="/images/logomarca.png" alt="Painel de Uso do Claude Code"></h1>
  <div class="header-controls">
    <div class="header-actions">
    <label id="theme-toggle-button" aria-label="Alternar tema entre claro e escuro" title="Alternar tema">
      <input type="checkbox" id="toggle">
      <svg viewBox="0 0 69.667 44" xmlns:xlink="http://www.w3.org/1999/xlink" xmlns="http://www.w3.org/2000/svg">
        <g transform="translate(3.5 3.5)" data-name="Component 15 – 1" id="Component_15_1">
          <g filter="url(#container)" transform="matrix(1, 0, 0, 1, -3.5, -3.5)"><rect fill="#83cbd8" transform="translate(3.5 3.5)" rx="17.5" height="35" width="60.667" data-name="container" id="container"></rect></g>
          <g transform="translate(2.333 2.333)" id="button"><g data-name="sun" id="sun"><g filter="url(#sun-outer)" transform="matrix(1, 0, 0, 1, -5.83, -5.83)"><circle fill="#f8e664" transform="translate(5.83 5.83)" r="15.167" cy="15.167" cx="15.167" data-name="sun-outer" id="sun-outer-2"></circle></g><g filter="url(#sun)" transform="matrix(1, 0, 0, 1, -5.83, -5.83)"><path fill="rgba(246,254,247,0.29)" transform="translate(9.33 9.33)" d="M11.667,0A11.667,11.667,0,1,1,0,11.667,11.667,11.667,0,0,1,11.667,0Z" data-name="sun" id="sun-3"></path></g><circle fill="#fcf4b9" transform="translate(8.167 8.167)" r="7" cy="7" cx="7" id="sun-inner"></circle></g><g data-name="moon" id="moon"><g filter="url(#moon)" transform="matrix(1, 0, 0, 1, -31.5, -5.83)"><circle fill="#cce6ee" transform="translate(31.5 5.83)" r="15.167" cy="15.167" cx="15.167" data-name="moon" id="moon-3"></circle></g><g fill="#a6cad0" transform="translate(-24.415 -1.009)" id="patches"><circle transform="translate(43.009 4.496)" r="2" cy="2" cx="2"></circle><circle transform="translate(39.366 17.952)" r="2" cy="2" cx="2" data-name="patch"></circle><circle transform="translate(33.016 8.044)" r="1" cy="1" cx="1" data-name="patch"></circle><circle transform="translate(51.081 18.888)" r="1" cy="1" cx="1" data-name="patch"></circle><circle transform="translate(33.016 22.503)" r="1" cy="1" cx="1" data-name="patch"></circle><circle transform="translate(50.081 10.53)" r="1.5" cy="1.5" cx="1.5" data-name="patch"></circle></g></g></g>
          <g filter="url(#cloud)" transform="matrix(1, 0, 0, 1, -3.5, -3.5)"><path fill="#fff" transform="translate(-3466.47 -160.94)" d="M3512.81,173.815a4.463,4.463,0,0,1,2.243.62.95.95,0,0,1,.72-1.281,4.852,4.852,0,0,1,2.623.519c.034.02-.5-1.968.281-2.716a2.117,2.117,0,0,1,2.829-.274,1.821,1.821,0,0,1,.854,1.858c.063.037,2.594-.049,3.285,1.273s-.865,2.544-.807,2.626a12.192,12.192,0,0,1,2.278.892c.553.448,1.106,1.992-1.62,2.927a7.742,7.742,0,0,1-3.762-.3c-1.28-.49-1.181-2.65-1.137-2.624s-1.417,2.2-2.623,2.2a4.172,4.172,0,0,1-2.394-1.206,3.825,3.825,0,0,1-2.771.774c-3.429-.46-2.333-3.267-2.2-3.55A3.721,3.721,0,0,1,3512.81,173.815Z" data-name="cloud" id="cloud"></path></g>
          <g fill="#def8ff" transform="translate(3.585 1.325)" id="stars"><path transform="matrix(-1, 0.017, -0.017, -1, 24.231, 3.055)" d="M.774,0,.566.559,0,.539.458.933.25,1.492l.485-.361.458.394L1.024.953,1.509.592.943.572Z"></path><path transform="matrix(-0.777, 0.629, -0.629, -0.777, 23.185, 12.358)" d="M1.341.529.836.472.736,0,.505.46,0,.4.4.729l-.231.46L.605.932l.4.326L.9.786Z" data-name="star"></path><path transform="matrix(0.438, 0.899, -0.899, 0.438, 23.177, 29.735)" d="M.015,1.065.475.9l.285.365L.766.772l.46-.164L.745.494.751,0,.481.407,0,.293.285.658Z" data-name="star"></path><path transform="translate(12.677 0.388) rotate(104)" d="M1.161,1.6,1.059,1,1.574.722.962.607.86,0,.613.572,0,.457.446.881.2,1.454l.516-.274Z" data-name="star"></path><path transform="matrix(-0.07, 0.998, -0.998, -0.07, 11.066, 15.457)" d="M.873,1.648l.114-.62L1.579.945,1.03.62,1.144,0,.706.464.157.139.438.7,0,1.167l.592-.083Z" data-name="star"></path><path transform="translate(8.326 28.061) rotate(11)" d="M.593,0,.638.724,0,.982l.7.211.045.724.36-.64.7.211L1.342.935,1.7.294,1.063.552Z" data-name="star"></path><path transform="translate(5.012 5.962) rotate(172)" d="M.816,0,.5.455,0,.311.323.767l-.312.455.516-.215.323.456L.827.911,1.343.7.839.552Z" data-name="star"></path><path transform="translate(2.218 14.616) rotate(169)" d="M1.261,0,.774.571.114.3.487.967,0,1.538.728,1.32l.372.662.047-.749.728-.218L1.215.749Z" data-name="star"></path></g>
        </g>
      </svg>
    </label>
    <label
      class="refresh-toggle"
      id="refresh-toggle"
      title="Pausar atualização automática"
      aria-label="Pausar atualização automática"
    >
      <input
        type="checkbox"
        id="refresh-toggle-input"
        class="refresh-toggle__input"
        checked
        onchange="onAutoRefreshToggle()"
      >
      <svg class="refresh-toggle__icon refresh-toggle__icon--pause" viewBox="0 0 24 24" aria-hidden="true">
        <path d="M6 4h4v16H6zM14 4h4v16h-4z"></path>
      </svg>
      <svg class="refresh-toggle__icon refresh-toggle__icon--play" viewBox="0 0 24 24" aria-hidden="true">
        <path d="M8 5v14l11-7z"></path>
      </svg>
    </label>
    <button id="rescan-btn" onclick="triggerRescan()" title="Reconstruir o banco de dados do zero, reprocessando todos os arquivos JSONL. Use se os dados estiverem desatualizados ou com custos incorretos.">&#x21bb; Reescanear</button>
  </div>
</header>

<div id="filter-bar">
  <div class="filter-label">Modelos</div>
  <div id="model-checkboxes"></div>
  <button class="filter-btn" onclick="selectAllModels()">Todos</button>
  <button class="filter-btn" onclick="clearAllModels()">Nenhum</button>
  <div class="filter-sep"></div>
  <div class="filter-label">Período</div>
  <div class="range-group">
    <button class="range-btn" data-range="1d"  onclick="setRange('1d')">Hoje</button>
    <button class="range-btn" data-range="7d"  onclick="setRange('7d')">7d</button>
    <button class="range-btn" data-range="30d" onclick="setRange('30d')">30d</button>
    <button class="range-btn" data-range="90d" onclick="setRange('90d')">90d</button>
    <button class="range-btn" data-range="180d" onclick="setRange('180d')">6m</button>
    <button class="range-btn" data-range="all" onclick="setRange('all')">Tudo</button>
  </div>
</div>

<div class="container">
  <div class="meta" id="meta">Carregando...</div>
  <div class="stats-row" id="stats-row"></div>
  <div class="usage-panel">
    <div class="section-title">Uso da Cota Claude (/usage)</div>
    <div id="usage-panel-content" class="usage-panel-grid"></div>
    <div class="usage-hint">Painel adicional com dados de <code>claude /usage --json</code> (quando disponível no ambiente).</div>
  </div>
  <div class="insights-card">
    <div class="section-title">Insights Acionáveis</div>
    <ul id="insights-list" class="insight-list"></ul>
  </div>
  <div class="charts-grid">
    <div class="chart-card wide">
      <h2 id="daily-chart-title">Uso Diário de Tokens</h2>
      <div class="chart-wrap tall"><canvas id="chart-daily"></canvas></div>
    </div>
    <div class="chart-card wide">
      <h2><span class="th-with-tooltip">Tendência de Uso (Entrada + Saída) <span class="tooltip" tabindex="0" aria-label="Ajuda sobre tendência de uso">?<span class="tooltip-text">Mostra o total diário de tokens de entrada + saída para os modelos e período selecionados. A linha tracejada representa a média móvel de 7 dias para facilitar a leitura da tendência.</span></span></span></h2>
      <div class="chart-wrap"><canvas id="chart-trend"></canvas></div>
    </div>
    <div class="chart-card">
      <h2>Por Modelo</h2>
      <div class="chart-wrap"><canvas id="chart-model"></canvas></div>
    </div>
    <div class="chart-card">
      <h2>Top Projetos por Tokens</h2>
      <div class="chart-wrap"><canvas id="chart-project"></canvas></div>
    </div>
    <div class="chart-card wide">
      <h2 class="chart-title-row"><span>Atividade por Hora</span><span class="tooltip" tabindex="0" aria-label="Ajuda sobre atividade por hora">?<span class="tooltip-text">Cada linha representa um horário (00:00–23:00) dentro do período filtrado. A barra indica a média de tokens (entrada + saída) por dia naquele horário, e o valor à direita mostra interações totais e média diária.</span></span></h2>
      <div id="hourly-activity-meta" class="hourly-meta"></div>
      <div id="hourly-activity-list" class="hourly-list"></div>
    </div>
  </div>
  <div class="table-card">
    <div class="section-title">Custo por Modelo</div>
    <table>
      <thead><tr>
        <th>Modelo</th>
        <th class="sortable" onclick="setModelSort('turns')">Interações <span class="sort-icon" id="msort-turns"></span></th>
        <th class="sortable" onclick="setModelSort('input')">Entrada <span class="sort-icon" id="msort-input"></span></th>
        <th class="sortable" onclick="setModelSort('output')">Saída <span class="sort-icon" id="msort-output"></span></th>
        <th class="sortable" onclick="setModelSort('cache_read')">Leitura de Cache <span class="sort-icon" id="msort-cache_read"></span></th>
        <th class="sortable" onclick="setModelSort('cache_creation')">Criação de Cache <span class="sort-icon" id="msort-cache_creation"></span></th>
        <th class="sortable" onclick="setModelSort('cost')"><span class="th-with-tooltip">Custo Estimado <span class="tooltip" tabindex="0" aria-label="Ajuda sobre custo estimado">?<span class="tooltip-text">Custo estimado considerando o preço em tokens de API. Não se aplica aos planos Max/Pro, pois esses planos funcionam por assinatura.</span></span></span> <span class="sort-icon" id="msort-cost"></span></th>
      </tr></thead>
      <tbody id="model-cost-body"></tbody>
    </table>
  </div>
  <div class="table-card">
    <div class="section-header"><div class="section-title">Sessões Recentes</div><button class="export-btn" onclick="exportSessionsCSV()" title="Exportar todas as sessões filtradas para CSV">&#x2913; CSV</button></div>
    <table>
      <thead><tr>
        <th>Sessão</th>
        <th>Projeto</th>
        <th>Nome sessão</th>
        <th class="sortable" onclick="setSessionSort('last')">Última Atividade <span class="sort-icon" id="sort-icon-last"></span></th>
        <th class="sortable" onclick="setSessionSort('duration_min')">Duração <span class="sort-icon" id="sort-icon-duration_min"></span></th>
        <th>Modelo</th>
        <th class="sortable" onclick="setSessionSort('turns')">Interações <span class="sort-icon" id="sort-icon-turns"></span></th>
        <th class="sortable" onclick="setSessionSort('input')">Entrada <span class="sort-icon" id="sort-icon-input"></span></th>
        <th class="sortable" onclick="setSessionSort('output')">Saída <span class="sort-icon" id="sort-icon-output"></span></th>
        <th class="sortable" onclick="setSessionSort('cost')"><span class="th-with-tooltip">Custo Estimado <span class="tooltip" tabindex="0" aria-label="Ajuda sobre custo estimado">?<span class="tooltip-text">Custo estimado considerando o preço em tokens de API. Não se aplica aos planos Max/Pro, pois esses planos funcionam por assinatura.</span></span></span> <span class="sort-icon" id="sort-icon-cost"></span></th>
        <th>Ação</th>
      </tr></thead>
      <tbody id="sessions-body"></tbody>
    </table>
    <div id="sessions-pager" class="table-footer"></div>
  </div>
  <div class="table-card">
    <div class="section-header"><div class="section-title">Custo por Projeto</div><button class="export-btn" onclick="exportProjectsCSV()" title="Exportar todos os projetos para CSV">&#x2913; CSV</button></div>
    <table>
      <thead><tr>
        <th>Projeto</th>
        <th class="sortable" onclick="setProjectSort('sessions')">Sessões <span class="sort-icon" id="psort-sessions"></span></th>
        <th class="sortable" onclick="setProjectSort('turns')">Interações <span class="sort-icon" id="psort-turns"></span></th>
        <th class="sortable" onclick="setProjectSort('input')">Entrada <span class="sort-icon" id="psort-input"></span></th>
        <th class="sortable" onclick="setProjectSort('output')">Saída <span class="sort-icon" id="psort-output"></span></th>
        <th class="sortable" onclick="setProjectSort('cost')"><span class="th-with-tooltip">Custo Estimado <span class="tooltip" tabindex="0" aria-label="Ajuda sobre custo estimado">?<span class="tooltip-text">Custo estimado considerando o preço em tokens de API. Não se aplica aos planos Max/Pro, pois esses planos funcionam por assinatura.</span></span></span> <span class="sort-icon" id="psort-cost"></span></th>
      </tr></thead>
      <tbody id="project-cost-body"></tbody>
    </table>
  </div>
</div>

<div id="toast-container" class="toast-container" aria-live="polite" aria-atomic="true"></div>

<div class="disclaimer-banner">
  <p><strong>Aviso de cobertura:</strong> este painel exibe apenas sessões registradas localmente pelo Claude Code (CLI/terminal).
  Sessões feitas via Claude Web ou aplicativo de desktop ainda não estão disponíveis.</p>
  <p><strong>Disclaimer de custo:</strong> estimativas de custo baseadas nos preços da API da Anthropic (<a href="https://claude.com/pricing#api" target="_blank">claude.com/pricing#api</a>) em abril de 2026. Apenas modelos contendo <em>opus</em>, <em>sonnet</em> ou <em>haiku</em> no nome são incluídos nos cálculos de custo. Custos reais para assinantes Max/Pro diferem do preço de API.</p>
</div>

<footer>
  <div class="footer-content">
    <p>
      GitHub (fork): <a href="https://github.com/alexbertozzi00/claude-usage" target="_blank">https://github.com/alexbertozzi00/claude-usage</a>
      <br>
      Fork por: Alexandre Bertozzi &nbsp;&middot;&nbsp; Licença: MIT
    </p>
  </div>
</footer>

<script>
// ── Helpers ────────────────────────────────────────────────────────────────
function esc(s) {
  const d = document.createElement('div');
  d.textContent = String(s);
  return d.innerHTML;
}

function showToast(message, type = 'info') {
  const container = document.getElementById('toast-container');
  if (!container) return;
  const el = document.createElement('div');
  el.className = 'toast ' + (type || 'info');
  el.textContent = String(message || '');
  container.appendChild(el);
  setTimeout(() => {
    el.remove();
  }, 2400);
}

// ── State ──────────────────────────────────────────────────────────────────
let rawData = null;
let selectedModels = new Set();
let selectedRange = '30d';
let charts = {};
let sessionSortCol = 'last';
let modelSortCol = 'cost';
let modelSortDir = 'desc';
let projectSortCol = 'cost';
let projectSortDir = 'desc';
let lastFilteredSessions = [];
let lastByProject = [];
let sessionSortDir = 'desc';
let sessionsPage = 1;
const SESSIONS_PAGE_SIZE = 15;
const renamingSessions = new Set();
const AUTO_REFRESH_INTERVAL_MS = 30000;
const AUTO_REFRESH_INTERVAL_SECONDS = AUTO_REFRESH_INTERVAL_MS / 1000;
const AUTO_REFRESH_STORAGE_KEY = 'ccu:autoRefreshPaused';
const MAX_CUSTOM_NAME_LENGTH = 80;
let autoRefreshCountdown = AUTO_REFRESH_INTERVAL_SECONDS;
let latestGeneratedAt = null;
let isAutoRefreshPaused = false;

function updateMetaStatus() {
  const meta = document.getElementById('meta');
  if (!meta) return;
  const generatedLabel = latestGeneratedAt ? ('Atualizado em: ' + latestGeneratedAt) : 'Atualizado em: -';
  const refreshLabel = isAutoRefreshPaused
    ? 'Atualização automática: pausada'
    : ('Atualização automática: ativa (em ' + autoRefreshCountdown + 's)');
  meta.textContent = generatedLabel + ' \u00b7 ' + refreshLabel;
}

function updateAutoRefreshToggleUI() {
  const toggleInput = document.getElementById('refresh-toggle-input');
  const toggleLabel = document.getElementById('refresh-toggle');
  if (toggleInput) {
    toggleInput.checked = !isAutoRefreshPaused;
  }
  if (toggleLabel) {
    const actionLabel = isAutoRefreshPaused ? 'Retomar atualização automática' : 'Pausar atualização automática';
    toggleLabel.title = actionLabel;
    toggleLabel.setAttribute('aria-label', actionLabel);
  }
}

function persistAutoRefreshState() {
  try {
    localStorage.setItem(AUTO_REFRESH_STORAGE_KEY, isAutoRefreshPaused ? 'true' : 'false');
  } catch (e) {
    console.warn('Falha ao salvar preferência de atualização automática.', e);
  }
}

function restoreAutoRefreshState() {
  try {
    const stored = localStorage.getItem(AUTO_REFRESH_STORAGE_KEY);
    isAutoRefreshPaused = stored === 'true';
  } catch (e) {
    isAutoRefreshPaused = false;
  }
  updateAutoRefreshToggleUI();
  updateMetaStatus();
}

function onAutoRefreshToggle() {
  const toggleInput = document.getElementById('refresh-toggle-input');
  if (!toggleInput) return;
  isAutoRefreshPaused = !toggleInput.checked;
  if (!isAutoRefreshPaused) {
    autoRefreshCountdown = AUTO_REFRESH_INTERVAL_SECONDS;
  }
  persistAutoRefreshState();
  updateAutoRefreshToggleUI();
  updateMetaStatus();
}

function startAutoRefreshCountdown() {
  setInterval(() => {
    if (isAutoRefreshPaused) {
      updateMetaStatus();
      return;
    }
    if (autoRefreshCountdown > 0) autoRefreshCountdown -= 1;
    updateMetaStatus();
  }, 1000);
}

function startAutoRefreshPolling() {
  setInterval(() => {
    if (isAutoRefreshPaused) return;
    loadData();
  }, AUTO_REFRESH_INTERVAL_MS);
}

// ── Pricing (Anthropic API, April 2026) ────────────────────────────────────
const PRICING = {
  'claude-opus-4-6':   { input:  5.00, output: 25.00, cache_write:  6.25, cache_read: 0.50 },
  'claude-opus-4-5':   { input:  5.00, output: 25.00, cache_write:  6.25, cache_read: 0.50 },
  'claude-sonnet-4-6': { input:  3.00, output: 15.00, cache_write:  3.75, cache_read: 0.30 },
  'claude-sonnet-4-5': { input:  3.00, output: 15.00, cache_write:  3.75, cache_read: 0.30 },
  'claude-haiku-4-5':  { input:  1.00, output:  5.00, cache_write:  1.25, cache_read: 0.10 },
  'claude-haiku-4-6':  { input:  1.00, output:  5.00, cache_write:  1.25, cache_read: 0.10 },
};

function isBillable(model) {
  if (!model) return false;
  const m = model.toLowerCase();
  return m.includes('opus') || m.includes('sonnet') || m.includes('haiku');
}

function getPricing(model) {
  if (!model) return null;
  if (PRICING[model]) return PRICING[model];
  for (const key of Object.keys(PRICING)) {
    if (model.startsWith(key)) return PRICING[key];
  }
  const m = model.toLowerCase();
  if (m.includes('opus'))   return PRICING['claude-opus-4-6'];
  if (m.includes('sonnet')) return PRICING['claude-sonnet-4-6'];
  if (m.includes('haiku'))  return PRICING['claude-haiku-4-5'];
  return null;
}

function calcCost(model, inp, out, cacheRead, cacheCreation) {
  if (!isBillable(model)) return 0;
  const p = getPricing(model);
  if (!p) return 0;
  return (
    inp           * p.input       / 1e6 +
    out           * p.output      / 1e6 +
    cacheRead     * p.cache_read  / 1e6 +
    cacheCreation * p.cache_write / 1e6
  );
}

// ── Formatting ─────────────────────────────────────────────────────────────
function fmt(n) {
  if (n === null || n === undefined) return '-';
  if (n >= 1e9) return (n/1e9).toFixed(2)+'B';
  if (n >= 1e6) return (n/1e6).toFixed(2)+'M';
  if (n >= 1e3) return (n/1e3).toFixed(1)+'K';
  return n.toLocaleString();
}
function fmtDate(isoDay) {
  if (!isoDay || isoDay.length < 10) return isoDay || '';
  const [y, m, d] = isoDay.slice(0, 10).split('-');
  if (!y || !m || !d) return isoDay;
  return `${d}/${m}/${y}`;
}
function fmtCost(c)    { return '$' + c.toFixed(4); }
function fmtCostBig(c) { return '$' + c.toFixed(2); }
function cssVar(name)  { return getComputedStyle(document.documentElement).getPropertyValue(name).trim(); }
function fmtPct(n) {
  if (n === null || n === undefined || Number.isNaN(Number(n))) return '-';
  return Number(n).toFixed(1) + '%';
}

function renderUsageBlock(title, block) {
  const usedTokens = block?.used_tokens;
  const availableTokens = block?.available_tokens;
  const limitTokens = block?.limit_tokens;
  const resetsAt = block?.resets_at || '-';
  return `
    <div class="usage-box">
      <h3>${esc(title)}</h3>
      <div class="usage-line"><strong>Gasto:</strong> ${fmtPct(block?.used_percent)} <span class="muted">(${fmt(usedTokens)} tokens)</span></div>
      <div class="usage-line"><strong>Restante:</strong> ${fmtPct(block?.available_percent)} <span class="muted">(${fmt(availableTokens)} tokens)</span></div>
      <div class="usage-line"><strong>Limite:</strong> ${fmt(limitTokens)} tokens</div>
      <div class="usage-line"><strong>Reset:</strong> ${esc(String(resetsAt))}</div>
    </div>
  `;
}

function renderUsagePanel(snapshot) {
  const el = document.getElementById('usage-panel-content');
  if (!el) return;
  if (!snapshot || !snapshot.ok) {
    const err = snapshot?.error ? esc(String(snapshot.error)) : 'Não foi possível obter o snapshot de uso agora.';
    el.innerHTML = `<div class="usage-error">${err}</div>`;
    return;
  }
  el.innerHTML =
    renderUsageBlock('Sessão atual', snapshot.current_session || {}) +
    renderUsageBlock('Semana atual', snapshot.current_week || {});
}

async function loadUsageSnapshot() {
  try {
    const resp = await fetch('/api/usage');
    const usage = await resp.json();
    renderUsagePanel(usage);
  } catch (e) {
    renderUsagePanel({ ok: false, error: 'Falha ao carregar /api/usage.' });
  }
}

// ── Chart colors ───────────────────────────────────────────────────────────
const TOKEN_COLORS = {
  input:          'rgba(79,142,247,0.8)',
  output:         'rgba(167,139,250,0.8)',
  cache_read:     'rgba(74,222,128,0.6)',
  cache_creation: 'rgba(251,191,36,0.6)',
};
const MODEL_COLORS = ['#d97757','#4f8ef7','#4ade80','#a78bfa','#fbbf24','#f472b6','#34d399','#60a5fa'];

// ── Time range ─────────────────────────────────────────────────────────────
const RANGE_LABELS = {
  '1d': 'Hoje',
  '7d': 'Últimos 7 dias',
  '30d': 'Últimos 30 dias',
  '90d': 'Últimos 90 dias',
  '180d': 'Últimos 6 meses',
  'all': 'Período completo',
};
const RANGE_TICKS  = { '1d': 6, '7d': 7, '30d': 15, '90d': 13, '180d': 16, 'all': 12 };

function getLatestDataDay() {
  if (!rawData) return null;
  const fromSessions = (rawData.sessions_all || []).map(s => s.last_date).filter(Boolean);
  const fromDaily = (rawData.daily_by_model || []).map(r => r.day).filter(Boolean);
  const allDays = fromSessions.concat(fromDaily);
  if (!allDays.length) return null;
  return allDays.reduce((max, d) => (d > max ? d : max), allDays[0]);
}

function getRangeDayCount(cutoff) {
  const latestDataDay = getLatestDataDay();
  if (!latestDataDay) return 1;
  const end = new Date(latestDataDay + 'T00:00:00Z');

  let start = null;
  if (cutoff) {
    start = new Date(cutoff + 'T00:00:00Z');
  } else {
    const fromSessions = (rawData?.sessions_all || []).map(s => s.last_date).filter(Boolean);
    const fromDaily = (rawData?.daily_by_model || []).map(r => r.day).filter(Boolean);
    const allDays = fromSessions.concat(fromDaily);
    const earliest = allDays.length ? allDays.reduce((min, d) => (d < min ? d : min), allDays[0]) : latestDataDay;
    start = new Date(earliest + 'T00:00:00Z');
  }

  const diff = Math.round((end - start) / 86400000) + 1;
  return Math.max(1, diff);
}

function getRangeCutoff(range) {
  if (range === '24h') range = '1d';
  if (range === 'all') return null;

  // "Hoje": sempre usa o dia corrente em UTC (00:00-23:59), independente
  // de qual seja o último dia presente no payload.
  if (range === '1d') {
    return new Date().toISOString().slice(0, 10);
  }
  const daysByRange = { '7d': 7, '30d': 30, '90d': 90, '180d': 180 };
  const days = daysByRange[range] || 30;

  // Use the latest day present in payload as reference. This avoids empty
  // dashboards when the client clock/timezone is skewed relative to data.
  const latestDataDay = getLatestDataDay();
  const base = latestDataDay ? new Date(latestDataDay + 'T00:00:00Z') : new Date();
  base.setUTCDate(base.getUTCDate() - days + 1);
  return base.toISOString().slice(0, 10);
}

function getRangeTimestampCutoff(range) {
  return null;
}

function readURLRange() {
  const p = new URLSearchParams(window.location.search).get('range');
  if (p === '24h') return '1d';
  return ['1d', '7d', '30d', '90d', '180d', 'all'].includes(p) ? p : '30d';
}

function readURLTheme() {
  const p = new URLSearchParams(window.location.search).get('theme');
  return ['light', 'dark'].includes(p) ? p : null;
}

function getInitialTheme() {
  const fromURL = readURLTheme();
  if (fromURL) return fromURL;
  const saved = localStorage.getItem('claude_usage_theme');
  if (saved === 'light' || saved === 'dark') return saved;
  return window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark';
}

function applyTheme(theme) {
  const resolved = theme === 'light' ? 'light' : 'dark';
  document.documentElement.dataset.theme = resolved;
  localStorage.setItem('claude_usage_theme', resolved);
  const toggle = document.getElementById('toggle');
  if (toggle) toggle.checked = resolved === 'dark';
  return resolved;
}

function toggleTheme() {
  const toggle = document.getElementById('toggle');
  if (!toggle) return;
  applyTheme(toggle.checked ? 'dark' : 'light');
  if (rawData) applyFilter();
}

function initThemeToggle() {
  const toggle = document.getElementById('toggle');
  if (!toggle) return;
  toggle.addEventListener('change', toggleTheme);
}

function setRange(range) {
  selectedRange = range;
  sessionsPage = 1;
  document.querySelectorAll('.range-btn').forEach(btn =>
    btn.classList.toggle('active', btn.dataset.range === range)
  );
  updateURL();
  applyFilter();
}

function getSelectedRangeLabel() {
  return RANGE_LABELS[selectedRange] || RANGE_LABELS['30d'];
}

// ── Model filter ───────────────────────────────────────────────────────────
function modelPriority(m) {
  const ml = m.toLowerCase();
  if (ml.includes('opus'))   return 0;
  if (ml.includes('sonnet')) return 1;
  if (ml.includes('haiku'))  return 2;
  return 3;
}

function readURLModels(allModels) {
  const param = new URLSearchParams(window.location.search).get('models');
  const billable = allModels.filter(m => isBillable(m));

  // Default behavior: prioritize billable Claude models for cost visibility.
  // If none exist, fall back to all models to avoid an empty dashboard.
  if (!param) return new Set((billable.length ? billable : allModels));

  // URL-pinned selection (models=...)
  const fromURL = new Set(param.split(',').map(s => s.trim()).filter(Boolean));
  const matched = allModels.filter(m => fromURL.has(m));
  if (matched.length) return new Set(matched);

  // If URL selection is stale (no matching models), gracefully fallback.
  return new Set((billable.length ? billable : allModels));
}

function isDefaultModelSelection(allModels) {
  const billable = allModels.filter(m => isBillable(m));
  if (selectedModels.size !== billable.length) return false;
  return billable.every(m => selectedModels.has(m));
}

function buildFilterUI(allModels) {
  const sorted = [...allModels].sort((a, b) => {
    const pa = modelPriority(a), pb = modelPriority(b);
    return pa !== pb ? pa - pb : a.localeCompare(b);
  });
  selectedModels = readURLModels(allModels);
  const container = document.getElementById('model-checkboxes');
  container.innerHTML = sorted.map(m => {
    const checked = selectedModels.has(m);
    return `<label class="model-cb-label ${checked ? 'checked' : ''}" data-model="${esc(m)}">
      <input type="checkbox" value="${esc(m)}" ${checked ? 'checked' : ''} onchange="onModelToggle(this)">
      ${esc(m)}
    </label>`;
  }).join('');
}

function onModelToggle(cb) {
  const label = cb.closest('label');
  if (cb.checked) { selectedModels.add(cb.value);    label.classList.add('checked'); }
  else            { selectedModels.delete(cb.value); label.classList.remove('checked'); }
  sessionsPage = 1;
  updateURL();
  applyFilter();
}

function selectAllModels() {
  document.querySelectorAll('#model-checkboxes input').forEach(cb => {
    cb.checked = true; selectedModels.add(cb.value); cb.closest('label').classList.add('checked');
  });
  sessionsPage = 1;
  updateURL(); applyFilter();
}

function clearAllModels() {
  document.querySelectorAll('#model-checkboxes input').forEach(cb => {
    cb.checked = false; selectedModels.delete(cb.value); cb.closest('label').classList.remove('checked');
  });
  sessionsPage = 1;
  updateURL(); applyFilter();
}

// ── URL persistence ────────────────────────────────────────────────────────
function updateURL() {
  const allModels = Array.from(document.querySelectorAll('#model-checkboxes input')).map(cb => cb.value);
  const params = new URLSearchParams();
  if (selectedRange !== '30d') params.set('range', selectedRange);
  if (!isDefaultModelSelection(allModels)) params.set('models', Array.from(selectedModels).join(','));
  const search = params.toString() ? '?' + params.toString() : '';
  history.replaceState(null, '', window.location.pathname + search);
}

// ── Session sort ───────────────────────────────────────────────────────────
function setSessionSort(col) {
  sessionsPage = 1;
  if (sessionSortCol === col) {
    sessionSortDir = sessionSortDir === 'desc' ? 'asc' : 'desc';
  } else {
    sessionSortCol = col;
    sessionSortDir = 'desc';
  }
  updateSortIcons();
  applyFilter();
}

function updateSortIcons() {
  document.querySelectorAll('.sort-icon').forEach(el => el.textContent = '');
  const icon = document.getElementById('sort-icon-' + sessionSortCol);
  if (icon) icon.textContent = sessionSortDir === 'desc' ? ' \u25bc' : ' \u25b2';
}

function sortSessions(sessions) {
  return [...sessions].sort((a, b) => {
    let av, bv;
    if (sessionSortCol === 'cost') {
      av = calcCost(a.model, a.input, a.output, a.cache_read, a.cache_creation);
      bv = calcCost(b.model, b.input, b.output, b.cache_read, b.cache_creation);
    } else if (sessionSortCol === 'duration_min') {
      av = parseFloat(a.duration_min) || 0;
      bv = parseFloat(b.duration_min) || 0;
    } else {
      av = a[sessionSortCol] ?? 0;
      bv = b[sessionSortCol] ?? 0;
    }
    if (av < bv) return sessionSortDir === 'desc' ? 1 : -1;
    if (av > bv) return sessionSortDir === 'desc' ? -1 : 1;
    return 0;
  });
}

function paginateSessions(items, page, pageSize) {
  const total = items.length;
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const safePage = Math.min(Math.max(1, page), totalPages);
  const start = (safePage - 1) * pageSize;
  return {
    items: items.slice(start, start + pageSize),
    page: safePage,
    total,
    totalPages,
  };
}

function renderCurrentSessionsPage() {
  const paged = paginateSessions(lastFilteredSessions, sessionsPage, SESSIONS_PAGE_SIZE);
  sessionsPage = paged.page;
  renderSessionsTable(paged.items);
  renderSessionsPager(paged);
}

function setSessionsPage(nextPage) {
  sessionsPage = nextPage;
  renderCurrentSessionsPage();
}

function renderSessionsPager(paged) {
  const el = document.getElementById('sessions-pager');
  if (!el) return;
  const hasRows = paged.total > 0;
  const from = hasRows ? ((paged.page - 1) * SESSIONS_PAGE_SIZE + 1) : 0;
  const to = hasRows ? (from + paged.items.length - 1) : 0;
  el.innerHTML = `
    <div>${hasRows ? `Mostrando ${from}-${to} de ${paged.total} sessões` : 'Nenhuma sessão encontrada para os filtros atuais.'}</div>
    <div class="pager">
      <button class="pager-btn" onclick="setSessionsPage(1)" ${paged.page <= 1 ? 'disabled' : ''}>&laquo; Primeira</button>
      <button class="pager-btn" onclick="setSessionsPage(${paged.page - 1})" ${paged.page <= 1 ? 'disabled' : ''}>&lsaquo; Anterior</button>
      <span class="pager-label">Página ${paged.page} de ${paged.totalPages}</span>
      <button class="pager-btn" onclick="setSessionsPage(${paged.page + 1})" ${paged.page >= paged.totalPages ? 'disabled' : ''}>Próxima &rsaquo;</button>
      <button class="pager-btn" onclick="setSessionsPage(${paged.totalPages})" ${paged.page >= paged.totalPages ? 'disabled' : ''}>Última &raquo;</button>
    </div>
  `;
}

// ── Aggregation & filtering ────────────────────────────────────────────────
function applyFilter() {
  if (!rawData) return;

  const cutoff = getRangeCutoff(selectedRange);
  const cutoffTs = getRangeTimestampCutoff(selectedRange);

  const filteredHourly = (rawData.hourly_by_model || []).filter(r => {
    if (!selectedModels.has(r.model)) return false;
    return !cutoff || r.day >= cutoff;
  });

  const filteredDaily = rawData.daily_by_model.filter(r =>
    selectedModels.has(r.model) && (!cutoff || r.day >= cutoff)
  );

  // Daily chart: aggregate by day
  const dailyMap = {};
  for (const r of filteredDaily) {
    if (!dailyMap[r.day]) dailyMap[r.day] = { day: r.day, input: 0, output: 0, cache_read: 0, cache_creation: 0 };
    const d = dailyMap[r.day];
    d.input          += r.input;
    d.output         += r.output;
    d.cache_read     += r.cache_read;
    d.cache_creation += r.cache_creation;
  }
  const daily = Object.values(dailyMap).sort((a, b) => a.day.localeCompare(b.day));

  // By model: aggregate tokens + turns from daily data
  const modelMap = {};
  for (const r of filteredDaily) {
    if (!modelMap[r.model]) modelMap[r.model] = { model: r.model, input: 0, output: 0, cache_read: 0, cache_creation: 0, turns: 0, sessions: 0 };
    const m = modelMap[r.model];
    m.input          += r.input;
    m.output         += r.output;
    m.cache_read     += r.cache_read;
    m.cache_creation += r.cache_creation;
    m.turns          += r.turns;
  }

  // Filter sessions by model + date range
  const filteredSessions = rawData.sessions_all.filter(s => {
    if (!selectedModels.has(s.model)) return false;
    return !cutoff || s.last_date >= cutoff;
  });

  // Add session counts into modelMap
  for (const s of filteredSessions) {
    if (modelMap[s.model]) modelMap[s.model].sessions++;
  }

  const byModel = Object.values(modelMap).sort((a, b) => (b.input + b.output) - (a.input + a.output));

  // By project: aggregate from filtered sessions
  const projMap = {};
  for (const s of filteredSessions) {
    if (!projMap[s.project]) projMap[s.project] = { project: s.project, input: 0, output: 0, cache_read: 0, cache_creation: 0, turns: 0, sessions: 0, cost: 0 };
    const p = projMap[s.project];
    p.input          += s.input;
    p.output         += s.output;
    p.cache_read     += s.cache_read;
    p.cache_creation += s.cache_creation;
    p.turns          += s.turns;
    p.sessions++;
    p.cost += calcCost(s.model, s.input, s.output, s.cache_read, s.cache_creation);
  }
  const byProject = Object.values(projMap).sort((a, b) => (b.input + b.output) - (a.input + a.output));

  // Totals
  const totals = {
    sessions:       filteredSessions.length,
    turns:          byModel.reduce((s, m) => s + m.turns, 0),
    input:          byModel.reduce((s, m) => s + m.input, 0),
    output:         byModel.reduce((s, m) => s + m.output, 0),
    cache_read:     byModel.reduce((s, m) => s + m.cache_read, 0),
    cache_creation: byModel.reduce((s, m) => s + m.cache_creation, 0),
    cost:           byModel.reduce((s, m) => s + calcCost(m.model, m.input, m.output, m.cache_read, m.cache_creation), 0),
  };

  const peakDay = daily.length
    ? daily.reduce((best, row) => ((row.input + row.output) > (best.input + best.output) ? row : best), daily[0])
    : null;
  const nonZeroDaily = daily.filter(row => (row.input + row.output) > 0);
  const lowDay = nonZeroDaily.length
    ? nonZeroDaily.reduce((best, row) => ((row.input + row.output) < (best.input + best.output) ? row : best), nonZeroDaily[0])
    : null;

  // Update daily chart title
  document.getElementById('daily-chart-title').textContent = 'Uso Diário de Tokens \u2014 ' + getSelectedRangeLabel();

  renderStats(totals);
  renderInsights(totals, byModel, byProject, peakDay, lowDay);
  renderDailyChart(daily);
  renderTrendChart(daily);
  renderModelChart(byModel);
  renderProjectChart(byProject);
  renderHourlyActivity(filteredHourly, cutoff, cutoffTs);
  lastFilteredSessions = sortSessions(filteredSessions);
  lastByProject = sortProjects(byProject);
  renderCurrentSessionsPage();
  renderModelCostTable(byModel);
  renderProjectCostTable(lastByProject.slice(0, 20));
}

// ── Renderers ──────────────────────────────────────────────────────────────
function renderStats(t) {
  const rangeLabel = getSelectedRangeLabel().toLowerCase();
  const stats = [
    { label: 'Sessões',       value: t.sessions.toLocaleString(), sub: rangeLabel },
    { label: 'Interações',          value: fmt(t.turns),                sub: rangeLabel },
    { label: 'Tokens de Entrada',   value: fmt(t.input),                sub: rangeLabel },
    { label: 'Tokens de Saída',  value: fmt(t.output),               sub: rangeLabel },
    { label: 'Leitura de Cache',     value: fmt(t.cache_read),           sub: 'do cache de prompt' },
    { label: 'Criação de Cache', value: fmt(t.cache_creation),       sub: 'gravações no cache de prompt' },
    { label: 'Custo Estimado',      value: fmtCostBig(t.cost),          sub: 'preço de API, abr/2026', color: cssVar('--green') },
  ];
  document.getElementById('stats-row').innerHTML = stats.map(s => `
    <div class="stat-card">
      <div class="label">${s.label}</div>
      <div class="value" style="${s.color ? 'color:' + s.color : ''}">${esc(s.value)}</div>
      ${s.sub ? `<div class="sub">${esc(s.sub)}</div>` : ''}
    </div>
  `).join('');
}

function renderInsights(totals, byModel, byProject, peakDay, lowDay) {
  const container = document.getElementById('insights-list');
  if (!container) return;

  if (!totals.turns) {
    container.innerHTML = '<li>Ainda não há dados para os filtros/período selecionados.</li>';
    return;
  }

  const cacheRatio = totals.input ? (totals.cache_read / totals.input) : 0;
  const outputRatio = totals.input ? (totals.output / totals.input) : 0;
  const topModel = byModel.length ? byModel[0] : null;
  const topProject = byProject.length ? byProject[0] : null;

  const insights = [];
  insights.push(
    cacheRatio < 0.15
      ? `Baixo reaproveitamento de cache (${(cacheRatio * 100).toFixed(1)}%): mantenha prompts de sistema estáveis para aumentar acertos de cache.`
      : `Bom reaproveitamento de cache (${(cacheRatio * 100).toFixed(1)}%): sua carga já está se beneficiando do cache de prompt.`
  );

  insights.push(
    outputRatio > 1.0
      ? `Relação saída/entrada alta (${outputRatio.toFixed(2)}x): considere respostas padrão mais curtas para tarefas rotineiras.`
      : `Relação saída/entrada equilibrada (${outputRatio.toFixed(2)}x): o nível de verbosidade parece sob controle.`
  );

  if (topModel) {
    insights.push(`Modelo principal neste recorte: ${esc(topModel.model)} (${fmt(topModel.input + topModel.output)} tokens).`);
  }
  if (topProject) {
    insights.push(`Projeto líder em volume de tokens: ${esc(topProject.project)} (${fmt(topProject.input + topProject.output)} tokens).`);
  }
  if (peakDay && peakDay.day) {
    insights.push(`Dia de pico: ${fmtDate(peakDay.day)} (${fmt(peakDay.input + peakDay.output)} tokens de entrada+saída).`);
  }
  if (lowDay && lowDay.day) {
    insights.push(`Menor consumo diário (desconsiderando dias sem uso): ${fmtDate(lowDay.day)} (${fmt(lowDay.input + lowDay.output)} tokens de entrada+saída).`);
  }

  container.innerHTML = insights.map(item => `<li>${item}</li>`).join('') +
    '<li class="hint">Os insights são atualizados automaticamente ao alterar filtros de modelo e período.</li>';
}

function renderDailyChart(daily) {
  const ctx = document.getElementById('chart-daily').getContext('2d');
  if (charts.daily) charts.daily.destroy();
  charts.daily = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: daily.map(d => fmtDate(d.day)),
      datasets: [
        { label: 'Entrada',        data: daily.map(d => d.input),          backgroundColor: TOKEN_COLORS.input,          stack: 'tokens' },
        { label: 'Saída',          data: daily.map(d => d.output),         backgroundColor: TOKEN_COLORS.output,         stack: 'tokens' },
        { label: 'Leitura de Cache',     data: daily.map(d => d.cache_read),     backgroundColor: TOKEN_COLORS.cache_read,     stack: 'tokens' },
        { label: 'Criação de Cache', data: daily.map(d => d.cache_creation), backgroundColor: TOKEN_COLORS.cache_creation, stack: 'tokens' },
      ]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { labels: { color: cssVar('--chart-text'), boxWidth: 12 } } },
      scales: {
        x: { ticks: { color: cssVar('--chart-text'), maxTicksLimit: RANGE_TICKS[selectedRange] }, grid: { color: cssVar('--chart-grid') } },
        y: { ticks: { color: cssVar('--chart-text'), callback: v => fmt(v) }, grid: { color: cssVar('--chart-grid') } },
      }
    }
  });
}

function movingAverage(values, windowSize) {
  const out = [];
  for (let i = 0; i < values.length; i++) {
    const start = Math.max(0, i - windowSize + 1);
    const slice = values.slice(start, i + 1);
    const avg = slice.reduce((sum, v) => sum + v, 0) / (slice.length || 1);
    out.push(avg);
  }
  return out;
}

function renderTrendChart(daily) {
  const canvas = document.getElementById('chart-trend');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  if (charts.trend) charts.trend.destroy();

  const labels = daily.map(d => fmtDate(d.day));
  const totalIO = daily.map(d => (d.input || 0) + (d.output || 0));
  const avg7d = movingAverage(totalIO, 7);

  charts.trend = new Chart(ctx, {
    type: 'line',
    data: {
      labels,
      datasets: [
        {
          label: 'Tokens (entrada + saída)',
          data: totalIO,
          borderColor: 'rgba(79,142,247,1)',
          backgroundColor: 'rgba(79,142,247,0.2)',
          tension: 0.25,
          fill: true,
          pointRadius: 2,
        },
        {
          label: 'Curva de tendência',
          data: avg7d,
          borderColor: 'rgba(217,119,87,1)',
          borderDash: [6, 4],
          tension: 0.25,
          fill: false,
          pointRadius: 0,
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { labels: { color: cssVar('--chart-text'), boxWidth: 12 } },
        tooltip: {
          callbacks: {
            label: ctx => ` ${ctx.dataset.label}: ${fmt(ctx.raw || 0)}`
          }
        }
      },
      scales: {
        x: {
          ticks: { color: cssVar('--chart-text'), maxTicksLimit: RANGE_TICKS[selectedRange] },
          grid: { color: cssVar('--chart-grid') }
        },
        y: {
          ticks: { color: cssVar('--chart-text'), callback: v => fmt(v) },
          grid: { color: cssVar('--chart-grid') }
        },
      }
    }
  });
}

function renderModelChart(byModel) {
  const ctx = document.getElementById('chart-model').getContext('2d');
  if (charts.model) charts.model.destroy();
  if (!byModel.length) { charts.model = null; return; }
  charts.model = new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: byModel.map(m => m.model),
      datasets: [{ data: byModel.map(m => m.input + m.output), backgroundColor: MODEL_COLORS, borderWidth: 2, borderColor: cssVar('--card') }]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: {
        legend: { position: 'bottom', labels: { color: cssVar('--chart-text'), boxWidth: 12, font: { size: 11 } } },
        tooltip: { callbacks: { label: ctx => ` ${ctx.label}: ${fmt(ctx.raw)} tokens` } }
      }
    }
  });
}

function renderProjectChart(byProject) {
  const top = byProject.slice(0, 10);
  const ctx = document.getElementById('chart-project').getContext('2d');
  if (charts.project) charts.project.destroy();
  if (!top.length) { charts.project = null; return; }
  charts.project = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: top.map(p => p.project.length > 22 ? '\u2026' + p.project.slice(-20) : p.project),
      datasets: [
        { label: 'Entrada', data: top.map(p => p.input),  backgroundColor: TOKEN_COLORS.input },
        { label: 'Saída',   data: top.map(p => p.output), backgroundColor: TOKEN_COLORS.output },
      ]
    },
    options: {
      indexAxis: 'y', responsive: true, maintainAspectRatio: false,
      plugins: { legend: { labels: { color: cssVar('--chart-text'), boxWidth: 12 } } },
      scales: {
        x: { ticks: { color: cssVar('--chart-text'), callback: v => fmt(v) }, grid: { color: cssVar('--chart-grid') } },
        y: { ticks: { color: cssVar('--chart-text'), font: { size: 11 } }, grid: { color: cssVar('--chart-grid') } },
      }
    }
  });
}

function renderHourlyActivity(hourlyRows, cutoff, cutoffTs) {
  const container = document.getElementById('hourly-activity-list');
  const meta = document.getElementById('hourly-activity-meta');
  if (!container) return;

  const base = Array.from({ length: 24 }, (_, hour) => ({
    hour: String(hour).padStart(2, '0'),
    turns: 0,
    tokens: 0,
  }));

  for (const row of hourlyRows) {
    const idx = Number.parseInt(row.hour, 10);
    if (Number.isNaN(idx) || idx < 0 || idx > 23) continue;
    base[idx].turns += row.turns || 0;
    base[idx].tokens += (row.input || 0) + (row.output || 0);
  }

  const dayCount = getRangeDayCount(cutoff);
  const withAverages = base.map(r => ({
    ...r,
    avgTurns: r.turns / dayCount,
    avgTokens: r.tokens / dayCount,
  }));
  const maxTokens = Math.max(1, ...withAverages.map(r => r.avgTokens));

  if (meta) {
    meta.textContent = `Período analisado: ${dayCount} dia(s). Barra = média de tokens (entrada + saída) por dia em cada horário.`;
  }

  const selectedModelsParam = encodeURIComponent(Array.from(selectedModels).join(','));
  const cutoffParam = encodeURIComponent(cutoff || '');
  const cutoffTsParam = encodeURIComponent(cutoffTs || '');
  const buildHourURL = (hour) => `/hour/${hour}?cutoff=${cutoffParam}&cutoff_ts=${cutoffTsParam}&models=${selectedModelsParam}`;

  container.innerHTML = withAverages.map(r => {
    const widthPct = (r.avgTokens / maxTokens) * 100;
    const hourURL = buildHourURL(r.hour);
    const turnsLabel = `${r.turns.toLocaleString()} (${r.avgTurns.toFixed(1)}/dia)`;
    const turnsCell = r.turns > 0
      ? `<a href="${hourURL}" class="session-link" title="Ver sessões deste horário">${turnsLabel}</a>`
      : turnsLabel;
    return `
      <div class="hourly-row">
        <div>${r.hour}:00</div>
        <div class="hourly-track"><div class="hourly-fill" style="width:${widthPct}%"></div></div>
        <div style="text-align:right">${turnsCell}</div>
      </div>
    `;
  }).join('');
}

function renderSessionsTable(sessions) {
  const formatSessionDuration = (durationMinRaw) => {
    const durationMin = Number.parseFloat(durationMinRaw);
    if (!Number.isFinite(durationMin) || durationMin < 0) return '0m';
    if (durationMin >= 60) return `${(durationMin / 60).toFixed(1)} h`;
    return `${durationMin}m`;
  };

  document.getElementById('sessions-body').innerHTML = sessions.map(s => {
    const cost = calcCost(s.model, s.input, s.output, s.cache_read, s.cache_creation);
    const costCell = isBillable(s.model)
      ? `<td class="cost">${fmtCost(cost)}</td>`
      : `<td class="cost-na">não se aplica</td>`;
    const sessionName = s.custom_name || '';
    const sessionURL = '/session/' + encodeURIComponent(s.session_id_full);
    const isSaving = renamingSessions.has(s.session_id_full);
    return `<tr>
      <td class="muted" style="font-family:monospace"><a class="session-link" href="${sessionURL}">${esc(s.session_id)}&hellip;</a></td>
      <td>${esc(s.project)}</td>
      <td>${esc(sessionName)}</td>
      <td class="muted">${esc(s.last)}</td>
      <td class="muted">${esc(formatSessionDuration(s.duration_min))}</td>
      <td><span class="model-tag">${esc(s.model)}</span></td>
      <td class="num">${s.turns}</td>
      <td class="num">${fmt(s.input)}</td>
      <td class="num">${fmt(s.output)}</td>
      ${costCell}
      <td><button class="rename-btn" onclick="renameSession('${esc(s.session_id_full)}')" ${isSaving ? 'disabled' : ''}>${isSaving ? 'Salvando...' : '✏️'}</button></td>
    </tr>`;
  }).join('');
}

async function renameSession(sessionId) {
  const session = rawData?.sessions_all?.find(s => s.session_id_full === sessionId);
  if (!session || renamingSessions.has(sessionId)) return;
  const currentName = session.custom_name || '';
  const newName = window.prompt('Digite o nome personalizado da sessão (vazio para remover):', currentName);
  if (newName === null) return;
  if (newName.length > MAX_CUSTOM_NAME_LENGTH) {
    showToast(`Nome muito longo (máximo ${MAX_CUSTOM_NAME_LENGTH} caracteres).`, 'error');
    return;
  }

  renamingSessions.add(sessionId);
  renderCurrentSessionsPage();
  showToast('Salvando nome...', 'info');
  try {
    const resp = await fetch('/api/session/rename', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        session_id: sessionId,
        custom_name: newName,
      }),
    });
    const data = await resp.json();
    if (!resp.ok || !data.ok) {
      throw new Error(data.error || 'Falha ao renomear sessão.');
    }
    session.custom_name = data.custom_name || '';
    showToast('Nome da sessão atualizado.', 'success');
    applyFilter();
  } catch (error) {
    console.error(error);
    showToast(error.message || 'Erro ao salvar nome.', 'error');
  } finally {
    renamingSessions.delete(sessionId);
    renderCurrentSessionsPage();
  }
}

function setModelSort(col) {
  if (modelSortCol === col) {
    modelSortDir = modelSortDir === 'desc' ? 'asc' : 'desc';
  } else {
    modelSortCol = col;
    modelSortDir = 'desc';
  }
  updateModelSortIcons();
  applyFilter();
}

function updateModelSortIcons() {
  document.querySelectorAll('[id^="msort-"]').forEach(el => el.textContent = '');
  const icon = document.getElementById('msort-' + modelSortCol);
  if (icon) icon.textContent = modelSortDir === 'desc' ? ' \u25bc' : ' \u25b2';
}

function sortModels(byModel) {
  return [...byModel].sort((a, b) => {
    let av, bv;
    if (modelSortCol === 'cost') {
      av = calcCost(a.model, a.input, a.output, a.cache_read, a.cache_creation);
      bv = calcCost(b.model, b.input, b.output, b.cache_read, b.cache_creation);
    } else {
      av = a[modelSortCol] ?? 0;
      bv = b[modelSortCol] ?? 0;
    }
    if (av < bv) return modelSortDir === 'desc' ? 1 : -1;
    if (av > bv) return modelSortDir === 'desc' ? -1 : 1;
    return 0;
  });
}

function renderModelCostTable(byModel) {
  document.getElementById('model-cost-body').innerHTML = sortModels(byModel).map(m => {
    const cost = calcCost(m.model, m.input, m.output, m.cache_read, m.cache_creation);
    const costCell = isBillable(m.model)
      ? `<td class="cost">${fmtCost(cost)}</td>`
      : `<td class="cost-na">não se aplica</td>`;
    return `<tr>
      <td><span class="model-tag">${esc(m.model)}</span></td>
      <td class="num">${fmt(m.turns)}</td>
      <td class="num">${fmt(m.input)}</td>
      <td class="num">${fmt(m.output)}</td>
      <td class="num">${fmt(m.cache_read)}</td>
      <td class="num">${fmt(m.cache_creation)}</td>
      ${costCell}
    </tr>`;
  }).join('');
}

// ── Project cost table sorting ────────────────────────────────────────────
function setProjectSort(col) {
  if (projectSortCol === col) {
    projectSortDir = projectSortDir === 'desc' ? 'asc' : 'desc';
  } else {
    projectSortCol = col;
    projectSortDir = 'desc';
  }
  updateProjectSortIcons();
  applyFilter();
}

function updateProjectSortIcons() {
  document.querySelectorAll('[id^="psort-"]').forEach(el => el.textContent = '');
  const icon = document.getElementById('psort-' + projectSortCol);
  if (icon) icon.textContent = projectSortDir === 'desc' ? ' \u25bc' : ' \u25b2';
}

function sortProjects(byProject) {
  return [...byProject].sort((a, b) => {
    const av = a[projectSortCol] ?? 0;
    const bv = b[projectSortCol] ?? 0;
    if (av < bv) return projectSortDir === 'desc' ? 1 : -1;
    if (av > bv) return projectSortDir === 'desc' ? -1 : 1;
    return 0;
  });
}

function renderProjectCostTable(byProject) {
  document.getElementById('project-cost-body').innerHTML = sortProjects(byProject).map(p => {
    return `<tr>
      <td>${esc(p.project)}</td>
      <td class="num">${p.sessions}</td>
      <td class="num">${fmt(p.turns)}</td>
      <td class="num">${fmt(p.input)}</td>
      <td class="num">${fmt(p.output)}</td>
      <td class="cost">${fmtCost(p.cost)}</td>
    </tr>`;
  }).join('');
}

// ── CSV Export ────────────────────────────────────────────────────────────
function csvField(val) {
  const s = String(val);
  if (s.includes(',') || s.includes('"') || s.includes('\n')) {
    return '"' + s.replace(/"/g, '""') + '"';
  }
  return s;
}

function csvTimestamp() {
  const d = new Date();
  return d.getFullYear() + '-' + String(d.getMonth()+1).padStart(2,'0') + '-' + String(d.getDate()).padStart(2,'0')
    + '_' + String(d.getHours()).padStart(2,'0') + String(d.getMinutes()).padStart(2,'0');
}

function downloadCSV(reportType, header, rows) {
  const lines = [header.map(csvField).join(',')];
  for (const row of rows) {
    lines.push(row.map(csvField).join(','));
  }
  const blob = new Blob([lines.join('\n')], { type: 'text/csv;charset=utf-8;' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = reportType + '_' + csvTimestamp() + '.csv';
  a.click();
  URL.revokeObjectURL(a.href);
}

function exportSessionsCSV() {
  const header = ['Sessão', 'Projeto', 'Nome sessão', 'Última atividade', 'Duração (min)', 'Modelo', 'Interações', 'Entrada', 'Saída', 'Leitura de cache', 'Criação de cache', 'Custo estimado'];
  const rows = lastFilteredSessions.map(s => {
    const cost = calcCost(s.model, s.input, s.output, s.cache_read, s.cache_creation);
    return [s.session_id, s.project, s.custom_name || '', s.last, s.duration_min, s.model, s.turns, s.input, s.output, s.cache_read, s.cache_creation, cost.toFixed(4)];
  });
  downloadCSV('sessoes', header, rows);
}

function exportProjectsCSV() {
  const header = ['Projeto', 'Sessões', 'Interações', 'Entrada', 'Saída', 'Leitura de cache', 'Criação de cache', 'Custo estimado'];
  const rows = lastByProject.map(p => {
    return [p.project, p.sessions, p.turns, p.input, p.output, p.cache_read, p.cache_creation, p.cost.toFixed(4)];
  });
  downloadCSV('projetos', header, rows);
}

// ── Rescan ────────────────────────────────────────────────────────────────
async function triggerRescan() {
  const btn = document.getElementById('rescan-btn');
  btn.disabled = true;
  btn.textContent = '\u21bb Escaneando...';
  try {
    const resp = await fetch('/api/rescan', { method: 'POST' });
    const d = await resp.json();
    btn.textContent = '\u21bb Reescanear (' + d.new + ' novos, ' + d.updated + ' atualizados)';
    await loadData();
  } catch(e) {
    btn.textContent = '\u21bb Reescanear (erro)';
    console.error(e);
  }
  setTimeout(() => { btn.textContent = '\u21bb Reescanear'; btn.disabled = false; }, 3000);
}

// ── Data loading ───────────────────────────────────────────────────────────
async function loadData() {
  try {
    const resp = await fetch('/api/data');
    const d = await resp.json();
    if (d.error) {
      document.body.innerHTML = '<div style="padding:40px;color:#f87171">' + esc(d.error) + '</div>';
      return;
    }
    latestGeneratedAt = d.generated_at;
    autoRefreshCountdown = AUTO_REFRESH_INTERVAL_SECONDS;
    updateMetaStatus();

    const isFirstLoad = rawData === null;
    rawData = d;

    if (isFirstLoad) {
      // Restore range from URL, mark active button
      selectedRange = readURLRange();
      document.querySelectorAll('.range-btn').forEach(btn =>
        btn.classList.toggle('active', btn.dataset.range === selectedRange)
      );
      // Build model filter (reads URL for model selection too)
      buildFilterUI(d.all_models);
      updateSortIcons();
      updateModelSortIcons();
      updateProjectSortIcons();
    }

    applyFilter();
    await loadUsageSnapshot();
  } catch(e) {
    console.error(e);
  }
}

applyTheme(getInitialTheme());
document.addEventListener('DOMContentLoaded', () => {
  initThemeToggle();
  restoreAutoRefreshState();
  startAutoRefreshCountdown();
  startAutoRefreshPolling();
  updateMetaStatus();
  loadData();
});
</script>
</body>
</html>
"""


class DashboardHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path in ("/", "/index.html"):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(HTML_TEMPLATE.encode("utf-8"))
        elif parsed.path == "/api/data":
            data = get_dashboard_data()
            body = json.dumps(data).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif parsed.path == "/api/usage":
            data = get_usage_snapshot()
            body = json.dumps(data).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif parsed.path.startswith("/hour/"):
            hour = unquote(parsed.path[len("/hour/"):]).strip()[:2]
            qs = parse_qs(parsed.query or "")
            cutoff = (qs.get("cutoff", [""])[0] or "").strip() or None
            cutoff_ts = (qs.get("cutoff_ts", [""])[0] or "").strip() or None
            models_raw = (qs.get("models", [""])[0] or "").strip()
            models = [m.strip() for m in models_raw.split(",") if m.strip()]
            data = get_sessions_for_hour(hour, cutoff=cutoff, cutoff_ts=cutoff_ts, models=models)
            body = render_hour_sessions_html(data).encode("utf-8")
            status_code = 404 if "error" in data else 200
            self.send_response(status_code)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif parsed.path.startswith("/session/"):
            session_id = unquote(parsed.path[len("/session/"):]).strip()
            session_data = get_session_history(session_id)
            body = render_session_history_html(session_data).encode("utf-8")
            status_code = 404 if "error" in session_data else 200
            self.send_response(status_code)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif parsed.path in ("/favicon.svg", "/favicon.ico", "/images/favicon.svg"):
            if not FAVICON_PATH.exists():
                self.send_response(404)
                self.end_headers()
                return
            body = FAVICON_PATH.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "image/svg+xml")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif parsed.path == "/images/logomarca.png":
            if not LOGOMARCA_PATH.exists():
                self.send_response(404)
                self.end_headers()
                return
            body = LOGOMARCA_PATH.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/rescan":
            # Full rebuild: delete DB and rescan from scratch
            try:
                if DB_PATH.exists():
                    DB_PATH.unlink()
                from scanner import scan
                result = scan(verbose=False)
            except Exception as e:
                result = {
                    "new": 0,
                    "updated": 0,
                    "skipped": 0,
                    "turns": 0,
                    "sessions": 0,
                    "error": str(e),
                }
            body = json.dumps(result).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif parsed.path == "/api/session/rename":
            content_length = int(self.headers.get("Content-Length", "0") or "0")
            body_raw = self.rfile.read(content_length) if content_length > 0 else b""
            try:
                payload = json.loads(body_raw.decode("utf-8") or "{}")
            except json.JSONDecodeError:
                payload = {}
            result, status_code = rename_session(
                session_id=(payload.get("session_id") or "").strip() if isinstance(payload, dict) else "",
                custom_name=(payload.get("custom_name") if isinstance(payload, dict) else ""),
            )
            body = json.dumps(result).encode("utf-8")
            self.send_response(status_code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()


def serve(host=None, port=None):
    host = host or os.environ.get("HOST", "localhost")
    port = port or int(os.environ.get("PORT", "8080"))
    server = HTTPServer((host, port), DashboardHandler)
    print(f"Dashboard running at http://{host}:{port}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    serve()

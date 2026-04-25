"""
codex_scanner.py - Layered Codex usage ingestion (MVP).

Strategy:
1) Primary source: local Codex logs/sessions from common directories.
2) Fallback: CLI capture (`codex` + `/usage`) via live_usage.capture_usage.
3) Fallback 2: manual JSON/CSV import file provided by the operator.
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path

from live_usage import capture_usage
from scanner import DB_PATH, get_db, init_db, aggregate_sessions, upsert_sessions, insert_turns

DEFAULT_CODEX_DIRS = [
    Path.home() / ".codex",
    Path.home() / ".config" / "codex",
]


@dataclass
class CodexUsageEvent:
    timestamp: str
    session_id: str
    model: str
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int = 0
    cache_creation_tokens: int = 0
    source_path: str = ""


def _nested_get(data, path, default=None):
    current = data
    for key in path:
        if not isinstance(current, dict):
            return default
        current = current.get(key)
        if current is None:
            return default
    return current


def _to_int(value):
    if value in (None, ""):
        return 0
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def _find_dict_with_keys(data, required_keys):
    """Depth-first search for a dict containing all required keys."""
    if isinstance(data, dict):
        if all(key in data for key in required_keys):
            return data
        for value in data.values():
            found = _find_dict_with_keys(value, required_keys)
            if found is not None:
                return found
    elif isinstance(data, list):
        for item in data:
            found = _find_dict_with_keys(item, required_keys)
            if found is not None:
                return found
    return None


def _extract_rollout_context(record):
    """Extract session/model defaults from Codex rollout lines."""
    if not isinstance(record, dict):
        return {}

    session_id = (
        record.get("session_id")
        or record.get("sessionId")
        or _nested_get(record, ["item", "session_id"])
        or _nested_get(record, ["item", "sessionId"])
        or _nested_get(record, ["item", "id"])
        or _nested_get(record, ["payload", "session_id"])
        or _nested_get(record, ["payload", "sessionId"])
    )
    model = (
        _nested_get(record, ["message", "model"], "")
        or record.get("model")
        or _nested_get(record, ["item", "model"])
        or _nested_get(record, ["item", "default_model"])
        or _nested_get(record, ["payload", "model"])
        or _nested_get(record, ["payload", "default_model"])
    )
    return {"session_id": session_id, "model": model}


def _extract_event(record, *, source_path, session_id_default=None, model_default=None):
    if not isinstance(record, dict):
        return None

    usage = _nested_get(record, ["message", "usage"], {}) if isinstance(_nested_get(record, ["message", "usage"], {}), dict) else {}
    rollout_usage = _find_dict_with_keys(record, {"input_tokens", "output_tokens"}) or {}

    input_tokens = _to_int(
        usage.get("input_tokens")
        or record.get("input_tokens")
        or rollout_usage.get("input_tokens")
        or record.get("prompt_tokens")
        or record.get("input")
    )
    output_tokens = _to_int(
        usage.get("output_tokens")
        or record.get("output_tokens")
        or rollout_usage.get("output_tokens")
        or record.get("completion_tokens")
        or record.get("output")
    )
    cache_read = _to_int(
        usage.get("cache_read_input_tokens")
        or record.get("cache_read_input_tokens")
        or record.get("cache_read_tokens")
        or rollout_usage.get("cache_read_input_tokens")
        or rollout_usage.get("cache_read_tokens")
    )
    cache_creation = _to_int(
        usage.get("cache_creation_input_tokens")
        or record.get("cache_creation_input_tokens")
        or record.get("cache_creation_tokens")
        or rollout_usage.get("cache_creation_input_tokens")
        or rollout_usage.get("cache_creation_tokens")
    )

    if input_tokens + output_tokens + cache_read + cache_creation == 0:
        return None

    return CodexUsageEvent(
        timestamp=(
            record.get("timestamp")
            or record.get("created_at")
            or datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
        ),
        session_id=(
            record.get("session_id")
            or record.get("sessionId")
            or record.get("conversation_id")
            or session_id_default
            or "codex-unknown-session"
        ),
        model=(
            _nested_get(record, ["message", "model"], "")
            or record.get("model")
            or model_default
            or "codex-unknown-model"
        ),
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cache_read_tokens=cache_read,
        cache_creation_tokens=cache_creation,
        source_path=str(source_path),
    )


def _parse_json_file(path):
    events = []
    errors = []
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception as exc:
        return [], [f"{path}: json inválido ({exc})"]

    if isinstance(data, list):
        iterable = data
    elif isinstance(data, dict):
        if isinstance(data.get("events"), list):
            iterable = data["events"]
        else:
            iterable = [data]
    else:
        iterable = []

    for item in iterable:
        event = _extract_event(item, source_path=path)
        if event:
            events.append(event)
    return events, errors


def _parse_jsonl_file(path):
    events = []
    errors = []
    current_session_id = None
    current_model = None
    try:
        with path.open(encoding="utf-8", errors="replace") as f:
            for idx, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    errors.append(f"{path}:{idx}: linha JSON inválida")
                    continue
                context = _extract_rollout_context(record)
                if context.get("session_id"):
                    current_session_id = context["session_id"]
                if context.get("model"):
                    current_model = context["model"]

                event = _extract_event(
                    record,
                    source_path=path,
                    session_id_default=current_session_id,
                    model_default=current_model,
                )
                if event:
                    events.append(event)
    except Exception as exc:
        errors.append(f"{path}: falha ao ler arquivo ({exc})")
    return events, errors


def _parse_csv_file(path):
    events = []
    errors = []
    try:
        with path.open(encoding="utf-8", errors="replace", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                event = _extract_event(row, source_path=path)
                if event:
                    events.append(event)
    except Exception as exc:
        errors.append(f"{path}: falha ao ler CSV ({exc})")
    return events, errors


def _parse_usage_file(path):
    ext = path.suffix.lower()
    if ext == ".jsonl":
        return _parse_jsonl_file(path)
    if ext == ".json":
        return _parse_json_file(path)
    if ext == ".csv":
        return _parse_csv_file(path)
    return [], []


def _scan_local_logs(logs_dirs):
    files = []
    for base in logs_dirs:
        base_path = Path(base)
        if not base_path.exists():
            continue
        files.extend(base_path.rglob("*.jsonl"))
        files.extend(base_path.rglob("*.json"))
        files.extend(base_path.rglob("*.csv"))

    events = []
    errors = []
    for file_path in sorted(set(files)):
        file_events, file_errors = _parse_usage_file(file_path)
        events.extend(file_events)
        errors.extend(file_errors)
    return events, errors, sorted(str(f) for f in set(files))


def _build_summary(events, *, source, errors, files_scanned, cli_snapshot=None):
    total_input = sum(e.input_tokens for e in events)
    total_output = sum(e.output_tokens for e in events)
    total_cache_read = sum(e.cache_read_tokens for e in events)
    total_cache_creation = sum(e.cache_creation_tokens for e in events)
    sessions = len({e.session_id for e in events})
    models = sorted({e.model for e in events})
    now = datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

    return {
        "provider": "codex",
        "captured_at": now,
        "source": source,
        "events": len(events),
        "sessions": sessions,
        "models": models,
        "totals": {
            "input_tokens": total_input,
            "output_tokens": total_output,
            "cache_read_tokens": total_cache_read,
            "cache_creation_tokens": total_cache_creation,
        },
        "files_scanned": files_scanned,
        "errors": errors,
        "cli_snapshot": cli_snapshot,
        "events_payload": [asdict(e) for e in events],
        "preview": [asdict(e) for e in events[:10]],
    }


def scan_codex_usage(logs_dirs=None, manual_import_file=None, timeout_seconds=12.0):
    logs_dirs = [Path(d) for d in (logs_dirs or DEFAULT_CODEX_DIRS)]
    events, errors, files_scanned = _scan_local_logs(logs_dirs)
    if events:
        return _build_summary(
            events,
            source="local_logs",
            errors=errors,
            files_scanned=files_scanned,
        )

    snapshot = capture_usage(timeout_seconds=timeout_seconds, provider="codex")
    if snapshot.ok:
        return _build_summary(
            [],
            source="cli_usage",
            errors=errors,
            files_scanned=files_scanned,
            cli_snapshot=asdict(snapshot),
        )

    if manual_import_file:
        manual_path = Path(manual_import_file)
        import_events, import_errors = _parse_usage_file(manual_path)
        errors.extend(import_errors)
        if import_events:
            return _build_summary(
                import_events,
                source="manual_import",
                errors=errors,
                files_scanned=files_scanned + [str(manual_path)],
            )

    errors.append(snapshot.error or "Sem dados de uso do Codex nas fontes disponíveis.")
    return _build_summary(
        [],
        source="none",
        errors=errors,
        files_scanned=files_scanned,
        cli_snapshot=asdict(snapshot),
    )


def ingest_codex_to_db(logs_dirs=None, manual_import_file=None, db_path=DB_PATH, timeout_seconds=12.0):
    result = scan_codex_usage(
        logs_dirs=logs_dirs,
        manual_import_file=manual_import_file,
        timeout_seconds=timeout_seconds,
    )
    events = result.get("events_payload", [])
    if result.get("source") not in {"local_logs", "manual_import"} or not events:
        result["db_ingest"] = {"inserted_turns": 0, "inserted_sessions": 0}
        return result

    turns = []
    session_metas = {}
    for event in events:
        provider = "codex"
        raw_session_id = event.get("session_id") or "codex-unknown-session"
        session_id = raw_session_id if str(raw_session_id).startswith("codex:") else f"codex:{raw_session_id}"
        timestamp = event.get("timestamp") or datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
        model = event.get("model") or "codex-unknown-model"
        source_path = event.get("source_path") or ""

        turns.append({
            "provider": provider,
            "session_id": session_id,
            "timestamp": timestamp,
            "model": model,
            "input_tokens": _to_int(event.get("input_tokens")),
            "output_tokens": _to_int(event.get("output_tokens")),
            "cache_read_tokens": _to_int(event.get("cache_read_tokens")),
            "cache_creation_tokens": _to_int(event.get("cache_creation_tokens")),
            "has_tool_marker": 0,
            "tool_name": None,
            "cwd": source_path,
            "message_id": "",
        })
        if session_id not in session_metas:
            session_metas[session_id] = {
                "session_id": session_id,
                "provider": provider,
                "project_name": "codex-import",
                "first_timestamp": timestamp,
                "last_timestamp": timestamp,
                "git_branch": "",
                "model": model,
            }
        else:
            meta = session_metas[session_id]
            meta["last_timestamp"] = max(meta["last_timestamp"], timestamp)
            if model and not meta["model"]:
                meta["model"] = model

    sessions = aggregate_sessions(list(session_metas.values()), turns)

    conn = get_db(db_path)
    init_db(conn)
    upsert_sessions(conn, sessions)
    insert_turns(conn, turns)
    conn.commit()
    conn.close()

    result["db_ingest"] = {"inserted_turns": len(turns), "inserted_sessions": len(sessions)}
    return result

"""OAuth usage integration for Claude Code internal usage endpoint."""

from __future__ import annotations

import json
import logging
import os
import time
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib import error, request

OAUTH_USAGE_URL = "https://api.anthropic.com/api/oauth/usage"
DEFAULT_TIMEOUT_SECONDS = 5.0
DEFAULT_CACHE_TTL_SECONDS = 45
ENV_FILE_PATH = Path(__file__).resolve().parent / ".env"
DOTENV_SEARCH_DEPTH = 5

logger = logging.getLogger(__name__)


_USAGE_CACHE: dict[str, Any] = {
    "expires_at": 0.0,
    "last_success": None,
    "last_snapshot": None,
}


def _iter_dotenv_candidates() -> list[Path]:
    candidates: list[Path] = []

    explicit_path = os.environ.get("CLAUDE_OAUTH_DOTENV_PATH")
    if explicit_path:
        candidates.append(Path(explicit_path).expanduser())

    cwd = Path.cwd().resolve()
    candidates.append(cwd / ".env")
    for parent in list(cwd.parents)[:DOTENV_SEARCH_DEPTH]:
        candidates.append(parent / ".env")

    candidates.append(ENV_FILE_PATH)

    # Keep insertion order while deduplicating.
    deduped: list[Path] = []
    seen: set[str] = set()
    for path in candidates:
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(path)
    return deduped


def _read_token_from_env_file(path: Path | None = None) -> str:
    env_paths = [path] if path else _iter_dotenv_candidates()
    try:
        for env_path in env_paths:
            if not env_path.exists() or not env_path.is_file():
                continue

            content = env_path.read_text(encoding="utf-8", errors="replace")
            for raw_line in content.splitlines():
                line = raw_line.strip().lstrip("﻿")
                if not line or line.startswith("#"):
                    continue
                if line.startswith("export "):
                    line = line[len("export "):].strip()
                if "=" not in line:
                    continue
                key, value = line.split("=", 1)
                if key.strip() != "CLAUDE_OAUTH_ACCESS_TOKEN":
                    continue
                normalized = value.strip().strip('"').strip("'")
                if normalized:
                    return normalized
    except OSError as exc:
        logger.warning("Falha ao ler .env para oauth usage: %s", exc)
    return ""


def _resolve_access_token(access_token: str | None) -> str:
    return (
        (access_token or "").strip()
        or (os.environ.get("CLAUDE_OAUTH_ACCESS_TOKEN") or "").strip()
        or _read_token_from_env_file()
    )


def _get_cached_snapshot(now: float) -> dict[str, Any] | None:
    snapshot = _USAGE_CACHE.get("last_snapshot")
    expires_at = float(_USAGE_CACHE.get("expires_at") or 0)
    if snapshot and expires_at > now:
        cached = deepcopy(snapshot)
        if cached.get("cache") == "miss":
            cached["cache"] = "hit"
        elif not cached.get("cache"):
            cached["cache"] = "hit"
        return cached
    return None


def _store_snapshot(snapshot: dict[str, Any], *, ttl_seconds: int, mark_success: bool = False) -> None:
    _USAGE_CACHE["last_snapshot"] = deepcopy(snapshot)
    _USAGE_CACHE["expires_at"] = time.time() + max(1, int(ttl_seconds))
    if mark_success:
        _USAGE_CACHE["last_success"] = deepcopy(snapshot)



def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _base_snapshot(raw: Any = None) -> dict[str, Any]:
    return {
        "currentWindowPercentage": None,
        "weeklyPercentage": None,
        "source": "oauth_usage",
        "fetchedAt": _iso_now(),
        "raw": raw if raw is not None else {},
    }


def _to_float_percent(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return max(0.0, min(100.0, float(value)))
    if isinstance(value, str):
        cleaned = value.strip().replace("%", "")
        try:
            parsed = float(cleaned)
            return max(0.0, min(100.0, parsed))
        except ValueError:
            return None
    return None


def _ratio_to_percent(used: Any, limit: Any) -> float | None:
    try:
        used_f = float(used)
        limit_f = float(limit)
    except (TypeError, ValueError):
        return None
    if limit_f <= 0:
        return None
    return max(0.0, min(100.0, (used_f / limit_f) * 100.0))


def _extract_percentage_from_node(node: Any) -> float | None:
    if not isinstance(node, dict):
        return None

    direct_keys = (
        "percent",
        "percentage",
        "utilization",
        "utilisation",
        "usage_percent",
        "used_percent",
        "percent_used",
        "usagePercentage",
    )
    for key in direct_keys:
        pct = _to_float_percent(node.get(key))
        if pct is not None:
            return pct

    for used_key, limit_key in (
        ("used", "limit"),
        ("usage", "limit"),
        ("consumed", "limit"),
        ("current", "max"),
        ("value", "max"),
    ):
        pct = _ratio_to_percent(node.get(used_key), node.get(limit_key))
        if pct is not None:
            return pct

    remaining_pct = _to_float_percent(node.get("remaining_percent"))
    if remaining_pct is not None:
        return max(0.0, min(100.0, 100.0 - remaining_pct))

    remaining = node.get("remaining")
    limit = node.get("limit")
    if remaining is not None and limit is not None:
        pct = _ratio_to_percent(remaining, limit)
        if pct is not None:
            return max(0.0, min(100.0, 100.0 - pct))

    return None


def _collect_named_nodes(payload: Any, name: str) -> list[Any]:
    matches: list[Any] = []

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            for k, v in node.items():
                if str(k).lower() == name.lower():
                    matches.append(v)
                walk(v)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(payload)
    return matches


def _extract_window_percentage(payload: Any, window_name: str) -> float | None:
    candidates = _collect_named_nodes(payload, window_name)
    for node in candidates:
        pct = _extract_percentage_from_node(node)
        if pct is not None:
            return pct

    # Fallback: sometimes the node may carry window metadata under another key.
    for node in candidates:
        if isinstance(node, dict):
            for value in node.values():
                pct = _extract_percentage_from_node(value)
                if pct is not None:
                    return pct

    return None


def _parse_usage_payload(payload: Any) -> dict[str, Any]:
    snapshot = _base_snapshot(raw=payload)
    snapshot["currentWindowPercentage"] = _extract_window_percentage(payload, "five_hour")
    snapshot["weeklyPercentage"] = _extract_window_percentage(payload, "seven_day")

    if snapshot["currentWindowPercentage"] is None or snapshot["weeklyPercentage"] is None:
        logger.info(
            "OAuth usage payload missing expected percentage fields",
            extra={
                "event": "oauth_usage_missing_percentage",
                "has_five_hour": bool(_collect_named_nodes(payload, "five_hour")),
                "has_seven_day": bool(_collect_named_nodes(payload, "seven_day")),
            },
        )

    return snapshot


def _build_error_snapshot(message: str, *, raw: Any = None, error_code: int | None = None) -> dict[str, Any]:
    snapshot = _base_snapshot(raw=raw)
    snapshot["error"] = {
        "message": message,
        "code": error_code,
    }
    return snapshot


def get_oauth_usage_snapshot(
    access_token: str | None = None,
    *,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    cache_ttl_seconds: int = DEFAULT_CACHE_TTL_SECONDS,
) -> dict[str, Any]:
    token = _resolve_access_token(access_token)
    now = time.time()

    cached_snapshot = _get_cached_snapshot(now)
    if cached_snapshot:
        return cached_snapshot

    if not token:
        snapshot = _build_error_snapshot(
            "OAuth access token ausente. Defina CLAUDE_OAUTH_ACCESS_TOKEN no ambiente ou no arquivo .env."
        )
        snapshot["cache"] = "miss"
        _store_snapshot(snapshot, ttl_seconds=min(120, max(15, int(cache_ttl_seconds))))
        return snapshot

    req = request.Request(
        OAUTH_USAGE_URL,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        },
        method="GET",
    )

    try:
        with request.urlopen(req, timeout=timeout_seconds) as resp:
            status = getattr(resp, "status", 200)
            raw_text = resp.read().decode("utf-8", errors="replace")

        payload = json.loads(raw_text) if raw_text else {}
        snapshot = _parse_usage_payload(payload)
        snapshot["httpStatus"] = status
        snapshot["cache"] = "miss"

        _store_snapshot(snapshot, ttl_seconds=cache_ttl_seconds, mark_success=True)
        return snapshot

    except error.HTTPError as http_err:
        body_text = http_err.read().decode("utf-8", errors="replace") if http_err.fp else ""
        body = None
        if body_text:
            try:
                body = json.loads(body_text)
            except json.JSONDecodeError:
                body = {"rawText": body_text}

        if http_err.code == 401 and isinstance(body, dict):
            err_obj = body.get("error") if isinstance(body.get("error"), dict) else {}
            err_type = str(err_obj.get("type") or "")
            err_msg = str(err_obj.get("message") or "")
            if err_type == "authentication_error" and "not supported" in err_msg.lower():
                snapshot = _build_error_snapshot(
                    "OAuth authentication não suportada pelo endpoint /api/oauth/usage para este token.",
                    raw=body,
                    error_code=401,
                )
                snapshot["authUnsupported"] = True
                snapshot["cache"] = "miss"
                _store_snapshot(snapshot, ttl_seconds=min(300, max(30, int(cache_ttl_seconds))))
                logger.warning("OAuth usage endpoint returned unsupported OAuth authentication (401)")
                return snapshot

        if http_err.code == 429 and _USAGE_CACHE["last_success"]:
            cached = deepcopy(_USAGE_CACHE["last_success"])
            cached["fallback"] = {
                "reason": "rate_limited",
                "httpStatus": 429,
            }
            cached["cache"] = "stale"
            logger.warning("OAuth usage rate-limited (429); serving cached snapshot")
            return cached

        logger.warning("OAuth usage request failed", extra={"event": "oauth_usage_http_error", "status": http_err.code})
        snapshot = _build_error_snapshot(
            f"Falha ao consultar oauth usage (HTTP {http_err.code}).",
            raw=body or {},
            error_code=http_err.code,
        )
        snapshot["cache"] = "miss"
        _store_snapshot(snapshot, ttl_seconds=min(120, max(15, int(cache_ttl_seconds))))
        return snapshot
    except error.URLError as url_err:
        logger.warning("OAuth usage request failed due to network error: %s", url_err)
        if _USAGE_CACHE["last_success"]:
            cached = deepcopy(_USAGE_CACHE["last_success"])
            cached["fallback"] = {"reason": "network_error"}
            cached["cache"] = "stale"
            return cached
        snapshot = _build_error_snapshot(f"Erro de rede ao consultar oauth usage: {url_err}")
        snapshot["cache"] = "miss"
        _store_snapshot(snapshot, ttl_seconds=min(120, max(15, int(cache_ttl_seconds))))
        return snapshot
    except json.JSONDecodeError as decode_err:
        logger.warning("OAuth usage response is not valid JSON: %s", decode_err)
        snapshot = _build_error_snapshot("Resposta do oauth usage não é JSON válido.")
        snapshot["cache"] = "miss"
        _store_snapshot(snapshot, ttl_seconds=min(120, max(15, int(cache_ttl_seconds))))
        return snapshot
    except Exception as exc:
        logger.exception("Unexpected error while fetching oauth usage")
        if _USAGE_CACHE["last_success"]:
            cached = deepcopy(_USAGE_CACHE["last_success"])
            cached["fallback"] = {"reason": "unexpected_error"}
            cached["cache"] = "stale"
            return cached
        snapshot = _build_error_snapshot(f"Erro inesperado ao consultar oauth usage: {exc}")
        snapshot["cache"] = "miss"
        _store_snapshot(snapshot, ttl_seconds=min(120, max(15, int(cache_ttl_seconds))))
        return snapshot

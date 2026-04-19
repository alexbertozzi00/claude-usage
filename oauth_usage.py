"""OAuth usage integration for Claude Code internal usage endpoint."""

from __future__ import annotations

import json
import logging
import os
import time
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any
from urllib import error, request

OAUTH_USAGE_URL = "https://api.anthropic.com/api/oauth/usage"
DEFAULT_TIMEOUT_SECONDS = 5.0
DEFAULT_CACHE_TTL_SECONDS = 45

logger = logging.getLogger(__name__)


_USAGE_CACHE: dict[str, Any] = {
    "expires_at": 0.0,
    "last_success": None,
}


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
    token = (access_token or os.environ.get("CLAUDE_OAUTH_ACCESS_TOKEN") or "").strip()
    now = time.time()

    if _USAGE_CACHE["last_success"] and _USAGE_CACHE["expires_at"] > now:
        cached = deepcopy(_USAGE_CACHE["last_success"])
        cached["cache"] = "hit"
        return cached

    if not token:
        return _build_error_snapshot(
            "OAuth access token ausente. Defina CLAUDE_OAUTH_ACCESS_TOKEN para habilitar oauth usage."
        )

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

        _USAGE_CACHE["last_success"] = deepcopy(snapshot)
        _USAGE_CACHE["expires_at"] = now + max(1, int(cache_ttl_seconds))
        return snapshot

    except error.HTTPError as http_err:
        body_text = http_err.read().decode("utf-8", errors="replace") if http_err.fp else ""
        body = None
        if body_text:
            try:
                body = json.loads(body_text)
            except json.JSONDecodeError:
                body = {"rawText": body_text}

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
        return _build_error_snapshot(
            f"Falha ao consultar oauth usage (HTTP {http_err.code}).",
            raw=body or {},
            error_code=http_err.code,
        )
    except error.URLError as url_err:
        logger.warning("OAuth usage request failed due to network error: %s", url_err)
        if _USAGE_CACHE["last_success"]:
            cached = deepcopy(_USAGE_CACHE["last_success"])
            cached["fallback"] = {"reason": "network_error"}
            cached["cache"] = "stale"
            return cached
        return _build_error_snapshot(f"Erro de rede ao consultar oauth usage: {url_err}")
    except json.JSONDecodeError as decode_err:
        logger.warning("OAuth usage response is not valid JSON: %s", decode_err)
        return _build_error_snapshot("Resposta do oauth usage não é JSON válido.")
    except Exception as exc:
        logger.exception("Unexpected error while fetching oauth usage")
        if _USAGE_CACHE["last_success"]:
            cached = deepcopy(_USAGE_CACHE["last_success"])
            cached["fallback"] = {"reason": "unexpected_error"}
            cached["cache"] = "stale"
            return cached
        return _build_error_snapshot(f"Erro inesperado ao consultar oauth usage: {exc}")

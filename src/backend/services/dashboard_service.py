"""Business logic helpers for dashboard backend."""

import sqlite3
from src.backend.config import MAX_CUSTOM_NAME_LENGTH, EFFICIENCY_OUTPUT_INPUT_CAP
from src.backend.repositories.dashboard_repository import (
    ensure_custom_name_column,
    get_session_by_id,
    update_session_custom_name,
)


def _clamp(value, low=0.0, high=100.0):
    return max(low, min(high, value))


def compute_efficiency_rankings(rows, top_n=None):
    """Compute normalized efficiency score (0-100) for session/project rows."""
    if not rows:
        return []

    prepared = []
    for row in rows:
        turns = max(0, int(row.get("turns") or 0))
        input_tokens = max(0, float(row.get("input") or 0))
        output_tokens = max(0, float(row.get("output") or 0))
        cache_read = max(0, float(row.get("cache_read") or 0))
        cost = float(row.get("cost") or 0.0)
        duration_min = max(0.0, float(row.get("duration_min") or 0.0))

        output_input_ratio = output_tokens / input_tokens if input_tokens > 0 else 0.0
        output_input_capped = min(output_input_ratio, EFFICIENCY_OUTPUT_INPUT_CAP)
        cache_read_pct = (cache_read / input_tokens * 100.0) if input_tokens > 0 else 0.0
        cost_per_turn = (cost / turns) if turns > 0 else 0.0
        turns_per_min = (turns / duration_min) if duration_min > 0 else None

        prepared.append({
            **row,
            "output_input_ratio": output_input_ratio,
            "output_input_capped": output_input_capped,
            "cache_read_pct": cache_read_pct,
            "cost_per_turn": cost_per_turn,
            "turns_per_min": turns_per_min,
        })

    max_cost_per_turn = max((r["cost_per_turn"] for r in prepared), default=0.0)
    max_turns_per_min = max((r["turns_per_min"] or 0.0 for r in prepared), default=0.0)

    ranking = []
    for row in prepared:
        output_input_score = _clamp((row["output_input_capped"] / EFFICIENCY_OUTPUT_INPUT_CAP) * 100.0)
        cache_read_score = _clamp(row["cache_read_pct"])
        if max_cost_per_turn <= 0:
            cost_per_turn_score = 100.0
        else:
            cost_per_turn_score = _clamp((1.0 - (row["cost_per_turn"] / max_cost_per_turn)) * 100.0)

        subscores = {
            "output_input": round(output_input_score, 2),
            "cache_read_pct": round(cache_read_score, 2),
            "cost_per_turn": round(cost_per_turn_score, 2),
        }

        if row["turns_per_min"] is not None:
            turns_per_min_score = 100.0 if max_turns_per_min <= 0 else _clamp((row["turns_per_min"] / max_turns_per_min) * 100.0)
            subscores["turns_per_min"] = round(turns_per_min_score, 2)

        score_total = round(sum(subscores.values()) / len(subscores), 2) if subscores else 0.0

        ranking.append({
            **row,
            "score_total": score_total,
            "subscores": subscores,
        })

    ranking.sort(key=lambda item: (-item["score_total"], -(item.get("turns") or 0), str(item.get("id") or item.get("project") or "")))
    if top_n is None:
        return ranking
    return ranking[:top_n]


def rename_session(session_id, custom_name, db_path):
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
        existing = get_session_by_id(conn, session_id)
        if existing is None:
            return {"ok": False, "error": "Sessão não encontrada."}, 404

        value = normalized if normalized else None
        update_session_custom_name(conn, session_id, value)
        return {
            "ok": True,
            "session_id": session_id,
            "custom_name": value,
        }, 200
    except sqlite3.Error as e:
        return {"ok": False, "error": f"Erro ao renomear sessão: {e}"}, 500
    finally:
        conn.close()

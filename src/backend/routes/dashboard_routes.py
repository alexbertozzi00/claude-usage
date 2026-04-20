"""HTTP route handlers for dashboard endpoints."""

import json
from dataclasses import asdict
from urllib.parse import parse_qs, unquote

from live_usage import capture_usage


def handle_get(handler, parsed, deps):
    if parsed.path in ("/", "/index.html"):
        body = deps["HTML_TEMPLATE"].encode("utf-8")
        handler.send_response(200)
        handler.send_header("Content-Type", "text/html; charset=utf-8")
        handler.send_header("Content-Length", str(len(body)))
        handler.end_headers()
        handler.wfile.write(body)
        return True

    if parsed.path == "/api/data":
        data = deps["get_dashboard_data"]()
        body = json.dumps(data).encode("utf-8")
        handler.send_response(200)
        handler.send_header("Content-Type", "application/json")
        handler.send_header("Content-Length", str(len(body)))
        handler.end_headers()
        handler.wfile.write(body)
        return True

    if parsed.path in ("/live-usage", "/live-usage/"):
        body = deps["LIVE_USAGE_HTML"].encode("utf-8")
        handler.send_response(200)
        handler.send_header("Content-Type", "text/html; charset=utf-8")
        handler.send_header("Content-Length", str(len(body)))
        handler.end_headers()
        handler.wfile.write(body)
        return True

    if parsed.path == "/api/live-usage":
        payload = json.dumps(asdict(capture_usage()), ensure_ascii=False).encode("utf-8")
        handler.send_response(200)
        handler.send_header("Content-Type", "application/json; charset=utf-8")
        handler.send_header("Content-Length", str(len(payload)))
        handler.end_headers()
        handler.wfile.write(payload)
        return True

    if parsed.path.startswith("/hour/"):
        hour = unquote(parsed.path[len("/hour/"):]).strip()[:2]
        qs = deps["parse_qs"](parsed.query or "")
        cutoff = (qs.get("cutoff", [""])[0] or "").strip() or None
        cutoff_ts = (qs.get("cutoff_ts", [""])[0] or "").strip() or None
        models_raw = (qs.get("models", [""])[0] or "").strip()
        models = [m.strip() for m in models_raw.split(",") if m.strip()]
        data = deps["get_sessions_for_hour"](hour, cutoff=cutoff, cutoff_ts=cutoff_ts, models=models)
        body = deps["render_hour_sessions_html"](data).encode("utf-8")
        handler.send_response(404 if "error" in data else 200)
        handler.send_header("Content-Type", "text/html; charset=utf-8")
        handler.send_header("Content-Length", str(len(body)))
        handler.end_headers()
        handler.wfile.write(body)
        return True

    if parsed.path.startswith("/session/"):
        session_id = unquote(parsed.path[len("/session/"):]).strip()
        session_data = deps["get_session_history"](session_id)
        body = deps["render_session_history_html"](session_data).encode("utf-8")
        handler.send_response(404 if "error" in session_data else 200)
        handler.send_header("Content-Type", "text/html; charset=utf-8")
        handler.send_header("Content-Length", str(len(body)))
        handler.end_headers()
        handler.wfile.write(body)
        return True

    if parsed.path in ("/ranking/help", "/help/ranking"):
        body = deps["render_ranking_help_html"]().encode("utf-8")
        handler.send_response(200)
        handler.send_header("Content-Type", "text/html; charset=utf-8")
        handler.send_header("Content-Length", str(len(body)))
        handler.end_headers()
        handler.wfile.write(body)
        return True

    if parsed.path in ("/trend/help", "/help/trend"):
        body = deps["render_trend_help_html"]().encode("utf-8")
        handler.send_response(200)
        handler.send_header("Content-Type", "text/html; charset=utf-8")
        handler.send_header("Content-Length", str(len(body)))
        handler.end_headers()
        handler.wfile.write(body)
        return True

    if parsed.path.startswith("/static/"):
        handler._serve_static(parsed.path)
        return True

    if parsed.path in ("/favicon.svg", "/favicon.ico", "/images/favicon.svg"):
        handler._serve_static("/static/images/favicon.svg")
        return True

    if parsed.path == "/images/logomarca.png":
        handler._serve_static("/static/images/logomarca.png")
        return True

    return False


def handle_post(handler, parsed, deps):
    if parsed.path == "/api/rescan":
        body = deps["do_rescan"]()
        handler.send_response(200)
        handler.send_header("Content-Type", "application/json")
        handler.send_header("Content-Length", str(len(body)))
        handler.end_headers()
        handler.wfile.write(body)
        return True

    if parsed.path == "/api/session/rename":
        content_length = int(handler.headers.get("Content-Length", "0") or "0")
        body_raw = handler.rfile.read(content_length) if content_length > 0 else b""
        try:
            payload = json.loads(body_raw.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            payload = {}
        result, status_code = deps["rename_session"](
            session_id=(payload.get("session_id") or "").strip() if isinstance(payload, dict) else "",
            custom_name=(payload.get("custom_name") if isinstance(payload, dict) else ""),
        )
        body = json.dumps(result).encode("utf-8")
        handler.send_response(status_code)
        handler.send_header("Content-Type", "application/json")
        handler.send_header("Content-Length", str(len(body)))
        handler.end_headers()
        handler.wfile.write(body)
        return True

    return False

"""HTTP route handlers for dashboard pages and APIs."""

from urllib.parse import unquote


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
        body = deps["json_dumps"](data).encode("utf-8")
        handler.send_response(200)
        handler.send_header("Content-Type", "application/json")
        handler.send_header("Content-Length", str(len(body)))
        handler.end_headers()
        handler.wfile.write(body)
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

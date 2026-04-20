"""HTTP route handlers for live usage page and API."""

from dataclasses import asdict

from src.backend.live_usage import capture_usage


def handle_live_usage_get(handler, parsed, deps):
    if parsed.path in ("/live-usage", "/live-usage/"):
        body = deps["LIVE_USAGE_HTML"].encode("utf-8")
        handler.send_response(200)
        handler.send_header("Content-Type", "text/html; charset=utf-8")
        handler.send_header("Content-Length", str(len(body)))
        handler.end_headers()
        handler.wfile.write(body)
        return True

    if parsed.path == "/api/live-usage":
        payload = deps["json_dumps"](asdict(capture_usage()), ensure_ascii=False).encode("utf-8")
        handler.send_response(200)
        handler.send_header("Content-Type", "application/json; charset=utf-8")
        handler.send_header("Content-Length", str(len(payload)))
        handler.end_headers()
        handler.wfile.write(payload)
        return True

    return False

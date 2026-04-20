"""HTTP route handlers for dashboard POST endpoints."""

import json


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

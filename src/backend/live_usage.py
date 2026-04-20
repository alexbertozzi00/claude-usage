"""
live_usage.py - Captura o painel /usage do Claude CLI e exibe em uma página web.
"""

from __future__ import annotations

import json
import os
import re
import select
import subprocess
import time
import webbrowser
from dataclasses import dataclass, asdict
from urllib.parse import urlparse
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path


ANSI_RE = re.compile(r"\x1B\[[0-?]*[ -/]*[@-~]")
CURRENT_SESSION_RE = re.compile(
    r"Current\s+session.*?(?P<used>\d{1,3})%\s*used.*?Resets\s+(?P<resets>.+?)(?:\n|\r)",
    re.IGNORECASE | re.DOTALL,
)
CURRENT_WEEK_RE = re.compile(
    r"Current\s+week\s*\(all\s+models\).*?(?P<used>\d{1,3})%\s*used.*?Resets\s+(?P<resets>.+?)(?:\n|\r)",
    re.IGNORECASE | re.DOTALL,
)

BASE_DIR = Path(__file__).resolve().parent
SRC_DIR = BASE_DIR.parent
TEMPLATES_DIR = SRC_DIR / "frontend" / "templates"
STATIC_DIR = SRC_DIR / "frontend" / "static"
LIVE_USAGE_HTML = (TEMPLATES_DIR / "pages" / "live_usage.html").read_text(encoding="utf-8")



@dataclass
class UsageBlock:
    used_percent: int | None = None
    available_percent: int | None = None
    resets_at: str = ""


@dataclass
class UsageSnapshot:
    ok: bool
    captured_at: str
    current_session: UsageBlock
    current_week: UsageBlock
    raw_excerpt: str = ""
    error: str = ""


def _strip_ansi(text: str) -> str:
    text = ANSI_RE.sub("", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return text


def _parse_block(pattern: re.Pattern[str], payload: str) -> UsageBlock:
    m = pattern.search(payload)
    if not m:
        return UsageBlock()

    used = int(m.group("used"))
    resets_at = " ".join((m.group("resets") or "").split())
    return UsageBlock(
        used_percent=used,
        available_percent=max(0, 100 - used),
        resets_at=resets_at,
    )


def capture_usage(timeout_seconds: float = 12.0) -> UsageSnapshot:
    if os.name == "nt":
        return UsageSnapshot(
            ok=False,
            captured_at=datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
            current_session=UsageBlock(),
            current_week=UsageBlock(),
            error="Live usage não é suportado no Windows (requer PTY/termios).",
        )

    import pty

    master_fd, slave_fd = pty.openpty()

    try:
        proc = subprocess.Popen(
            ["claude"],
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=slave_fd,
            text=False,
            env={**os.environ, "TERM": os.environ.get("TERM", "xterm-256color")},
        )
    except FileNotFoundError:
        os.close(master_fd)
        os.close(slave_fd)
        return UsageSnapshot(
            ok=False,
            captured_at=datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
            current_session=UsageBlock(),
            current_week=UsageBlock(),
            error="Comando 'claude' não encontrado no PATH.",
        )

    os.close(slave_fd)
    chunks: list[bytes] = []
    start = time.time()

    def write_line(cmd: str) -> None:
        os.write(master_fd, cmd.encode("utf-8") + b"\n")

    try:
        time.sleep(0.8)
        write_line("/usage")

        found_used = False
        while time.time() - start < timeout_seconds:
            ready, _, _ = select.select([master_fd], [], [], 0.25)
            if not ready:
                continue
            data = os.read(master_fd, 8192)
            if not data:
                break
            chunks.append(data)
            clean = _strip_ansi(b"".join(chunks).decode("utf-8", errors="replace"))
            if "% used" in clean:
                found_used = True
                if "Current week" in clean and "Current session" in clean:
                    break

        write_line("/exit")
        time.sleep(0.2)
    except Exception as exc:
        return UsageSnapshot(
            ok=False,
            captured_at=datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
            current_session=UsageBlock(),
            current_week=UsageBlock(),
            error=f"Falha ao capturar saída do Claude CLI: {exc}",
        )
    finally:
        try:
            proc.terminate()
            proc.wait(timeout=1)
        except Exception:
            pass
        os.close(master_fd)

    raw = b"".join(chunks).decode("utf-8", errors="replace")
    clean = _strip_ansi(raw)

    current_session = _parse_block(CURRENT_SESSION_RE, clean)
    current_week = _parse_block(CURRENT_WEEK_RE, clean)
    ok = bool(found_used and (current_session.used_percent is not None or current_week.used_percent is not None))

    return UsageSnapshot(
        ok=ok,
        captured_at=datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        current_session=current_session,
        current_week=current_week,
        raw_excerpt=clean[-1200:],
        error="" if ok else "Não foi possível extrair os dados de /usage.",
    )


class LiveUsageHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path in ("/", "/index.html", "/live-usage", "/live-usage/"):
            body = LIVE_USAGE_HTML.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if parsed.path == "/api/live-usage":
            snapshot = capture_usage()
            payload = json.dumps(asdict(snapshot), ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return

        if parsed.path.startswith("/static/"):
            rel = parsed.path[len("/static/"):].lstrip("/")
            fs_path = (STATIC_DIR / rel).resolve()
            if not str(fs_path).startswith(str(STATIC_DIR.resolve())) or not fs_path.exists() or not fs_path.is_file():
                self.send_response(404)
                self.end_headers()
                return
            ctype = {".css": "text/css; charset=utf-8", ".js": "application/javascript; charset=utf-8", ".svg": "image/svg+xml", ".png": "image/png"}.get(fs_path.suffix.lower(), "application/octet-stream")
            body = fs_path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        self.send_response(404)
        self.end_headers()


def serve_live_usage(host: str | None = None, port: int | None = None, open_tab: bool = True) -> None:
    host = host or os.environ.get("HOST", "localhost")
    port = int(port or os.environ.get("LIVE_USAGE_PORT", "8787"))

    server = HTTPServer((host, port), LiveUsageHandler)
    url = f"http://{host}:{port}"
    print(f"Live usage em {url}")
    print("Pressione Ctrl+C para encerrar.")

    if open_tab:
        webbrowser.open_new_tab(url)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nEncerrado.")


if __name__ == "__main__":
    serve_live_usage()

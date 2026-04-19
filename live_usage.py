"""
live_usage.py - Captura o painel /usage do Claude CLI e exibe em uma página web.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import subprocess
import time
import webbrowser
from dataclasses import dataclass, asdict
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer


ANSI_RE = re.compile(r"\x1B\[[0-?]*[ -/]*[@-~]")
CURRENT_SESSION_RE = re.compile(
    r"Current\s+session.*?(?P<used>\d{1,3})%\s*used.*?Resets\s+(?P<resets>.+?)(?:\n|\r)",
    re.IGNORECASE | re.DOTALL,
)
CURRENT_WEEK_RE = re.compile(
    r"Current\s+week\s*\(all\s+models\).*?(?P<used>\d{1,3})%\s*used.*?Resets\s+(?P<resets>.+?)(?:\n|\r)",
    re.IGNORECASE | re.DOTALL,
)


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
    mode: str = "unknown"
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


def _read_timeout_seconds(default: float = 12.0) -> float:
    raw = (os.environ.get("LIVE_USAGE_TIMEOUT") or "").strip()
    if not raw:
        return default
    try:
        value = float(raw)
        return max(1.0, min(value, 120.0))
    except Exception:
        return default


def capture_usage(timeout_seconds: float | None = None) -> UsageSnapshot:
    timeout_seconds = float(timeout_seconds or _read_timeout_seconds())
    if os.name == "nt":
        return _capture_usage_windows(timeout_seconds=timeout_seconds)
    return _capture_usage_posix(timeout_seconds=timeout_seconds)


def _resolve_claude_command() -> list[str] | None:
    """
    Resolve o comando do Claude CLI.

    Prioridade:
    1) variável de ambiente CLAUDE_BIN (aceita comando completo)
    2) binários comuns no PATH (claude/claude.cmd/claude.exe/claude.bat)
    """
    from_env = (os.environ.get("CLAUDE_BIN") or "").strip()
    if from_env:
        return shlex.split(from_env, posix=(os.name != "nt"))

    candidates = ["claude", "claude.cmd", "claude.exe", "claude.bat"]
    for name in candidates:
        found = shutil.which(name)
        if found:
            return [found]
    return None


def _claude_not_found_error() -> str:
    return (
        "Comando 'claude' não encontrado no PATH. "
        "Instale o Claude Code CLI e/ou defina a variável CLAUDE_BIN "
        "(ex.: CLAUDE_BIN='claude' ou CLAUDE_BIN='C:\\\\...\\\\claude.cmd')."
    )


def _try_direct_usage_command(claude_cmd: list[str], timeout_seconds: float) -> str:
    """
    Tenta obter o /usage em modo direto (sem sessão interativa),
    por exemplo: `claude /usage`.
    """
    attempts = [
        [*claude_cmd, "/usage"],
        [*claude_cmd, "usage"],
    ]
    for cmd in attempts:
        try:
            done = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=max(4.0, timeout_seconds),
            )
        except Exception:
            continue

        merged = (done.stdout or "") + "\n" + (done.stderr or "")
        clean = _strip_ansi(merged)
        if clean.strip():
            return clean
    return ""


def _snapshot_from_clean_text(clean: str, fallback_error: str = "") -> UsageSnapshot:
    current_session = _parse_block(CURRENT_SESSION_RE, clean)
    current_week = _parse_block(CURRENT_WEEK_RE, clean)
    found_used = "% used" in clean
    ok = bool(found_used and (current_session.used_percent is not None or current_week.used_percent is not None))
    return UsageSnapshot(
        ok=ok,
        captured_at=datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        current_session=current_session,
        current_week=current_week,
        mode="parsed",
        raw_excerpt=clean[-1200:],
        error="" if ok else (fallback_error or "Não foi possível extrair os dados de /usage."),
    )


def _capture_usage_windows(timeout_seconds: float = 12.0) -> UsageSnapshot:
    """Fallback para Windows sem dependências externas (sem pty/termios)."""
    claude_cmd = _resolve_claude_command()
    if not claude_cmd:
        return UsageSnapshot(
            ok=False,
            captured_at=datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
            current_session=UsageBlock(),
            current_week=UsageBlock(),
            error=_claude_not_found_error(),
        )

    direct = _try_direct_usage_command(claude_cmd, timeout_seconds)
    if direct:
        snap = _snapshot_from_clean_text(direct)
        if snap.ok:
            snap.mode = "direct"
            return snap

    try:
        proc = subprocess.Popen(
            claude_cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except FileNotFoundError:
        return UsageSnapshot(
            ok=False,
            captured_at=datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
            current_session=UsageBlock(),
            current_week=UsageBlock(),
            error=_claude_not_found_error(),
        )
    try:
        output, _ = proc.communicate("/usage\n/exit\n", timeout=timeout_seconds)
    except subprocess.TimeoutExpired as exc:
        try:
            proc.kill()
        except Exception:
            pass
        partial = _strip_ansi((exc.output or "") if isinstance(exc.output, str) else "")
        return UsageSnapshot(
            ok=False,
            captured_at=datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
            current_session=UsageBlock(),
            current_week=UsageBlock(),
            mode="interactive-timeout",
            raw_excerpt=partial[-1200:],
            error=(
                "Falha ao capturar saída do Claude CLI: timeout. "
                "Tente usar `claude /usage` manualmente para validar o modo comando no seu ambiente."
            ),
        )
    except Exception as exc:
        return UsageSnapshot(
            ok=False,
            captured_at=datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
            current_session=UsageBlock(),
            current_week=UsageBlock(),
            mode="interactive-error",
            error=f"Falha ao capturar saída do Claude CLI: {exc}",
        )

    raw = output or ""
    clean = _strip_ansi(raw)
    snap = _snapshot_from_clean_text(
        clean,
        fallback_error=(
            "Não foi possível extrair os dados de /usage no Windows sem PTY. "
            "Se persistir, execute em WSL/Git Bash ou instale um backend de terminal compatível com ConPTY."
        ),
    )
    snap.mode = "interactive"
    return snap


def _capture_usage_posix(timeout_seconds: float = 12.0) -> UsageSnapshot:
    import pty
    import select

    claude_cmd = _resolve_claude_command()
    if not claude_cmd:
        return UsageSnapshot(
            ok=False,
            captured_at=datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
            current_session=UsageBlock(),
            current_week=UsageBlock(),
            error=_claude_not_found_error(),
        )

    master_fd, slave_fd = pty.openpty()

    try:
        proc = subprocess.Popen(
            claude_cmd,
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
            error=_claude_not_found_error(),
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
            mode="interactive-error",
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
        mode="interactive",
        raw_excerpt=clean[-1200:],
        error="" if ok else "Não foi possível extrair os dados de /usage.",
    )


HTML = """<!doctype html>
<html lang=\"pt-BR\">
<head>
<meta charset=\"utf-8\" />
<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\" />
<title>Claude Live Usage</title>
<style>
  body { font-family: Inter, system-ui, sans-serif; background: #0b1020; color: #e5e7eb; margin: 0; }
  .wrap { max-width: 920px; margin: 24px auto; padding: 0 16px; }
  .head { display:flex; justify-content:space-between; align-items:center; margin-bottom:12px; }
  .btn { border:1px solid #334155; background:#111827; color:#e5e7eb; padding:8px 12px; border-radius:8px; cursor:pointer; }
  .grid { display:grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap:12px; }
  .card { border:1px solid #334155; background:#111827; border-radius:12px; padding:14px; }
  .title { color:#93c5fd; font-weight:700; margin-bottom:8px; }
  .big { font-size:34px; font-weight:800; line-height:1; }
  .muted { color:#94a3b8; font-size:13px; }
  pre { white-space:pre-wrap; word-break:break-word; max-height: 220px; overflow:auto; background:#020617; border:1px solid #1e293b; padding:10px; border-radius:8px; }
  .err { color: #fca5a5; }
</style>
</head>
<body>
<div class=\"wrap\">
  <div class=\"head\">
    <h1>Uso ao vivo do Claude CLI (/usage)</h1>
    <button class=\"btn\" onclick=\"reloadNow()\">Atualizar agora</button>
  </div>
  <p class=\"muted\" id=\"meta\">Carregando...</p>
  <div class=\"grid\">
    <div class=\"card\">
      <div class=\"title\">Current session</div>
      <div class=\"big\" id=\"session-avail\">-</div>
      <p class=\"muted\" id=\"session-used\"></p>
      <p class=\"muted\" id=\"session-reset\"></p>
    </div>
    <div class=\"card\">
      <div class=\"title\">Current week (all models)</div>
      <div class=\"big\" id=\"week-avail\">-</div>
      <p class=\"muted\" id=\"week-used\"></p>
      <p class=\"muted\" id=\"week-reset\"></p>
    </div>
  </div>
  <div class=\"card\" style=\"margin-top:12px\">
    <div class=\"title\">Saída capturada (debug)</div>
    <p class=\"muted err\" id=\"error\"></p>
    <pre id=\"raw\"></pre>
  </div>
</div>
<script>
async function loadUsage() {
  const res = await fetch('/api/live-usage');
  const data = await res.json();

  const meta = document.getElementById('meta');
  const s = data.current_session || {};
  const w = data.current_week || {};
  const mode = data.mode || 'unknown';

  document.getElementById('session-avail').textContent = s.available_percent == null ? '-' : s.available_percent + '% disponível';
  document.getElementById('session-used').textContent = s.used_percent == null ? '' : ('Usado: ' + s.used_percent + '%');
  document.getElementById('session-reset').textContent = s.resets_at ? ('Renova: ' + s.resets_at) : '';

  document.getElementById('week-avail').textContent = w.available_percent == null ? '-' : w.available_percent + '% disponível';
  document.getElementById('week-used').textContent = w.used_percent == null ? '' : ('Usado: ' + w.used_percent + '%');
  document.getElementById('week-reset').textContent = w.resets_at ? ('Renova: ' + w.resets_at) : '';

  document.getElementById('raw').textContent = data.raw_excerpt || '';
  document.getElementById('error').textContent = data.error || '';
  meta.textContent = 'Última captura: ' + (data.captured_at || '-') + ' · modo: ' + mode + (data.ok ? '' : ' (falha ao interpretar)');
}

function reloadNow(){ loadUsage().catch(console.error); }
setInterval(() => loadUsage().catch(console.error), 30000);
loadUsage().catch(console.error);
</script>
</body>
</html>
"""


class LiveUsageHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            body = HTML.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if self.path == "/api/live-usage":
            snapshot = capture_usage()
            payload = json.dumps(asdict(snapshot), ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
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

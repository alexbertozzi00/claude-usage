"""Stable public backend application API."""

import threading
import time
import webbrowser

from src.backend.config import HOST, PORT


def run_dashboard(projects_dir=None, open_browser=True):
    from cli import cmd_scan
    from src.backend.dashboard import serve

    print("Running scan first...")
    cmd_scan(projects_dir=projects_dir)

    print("\nStarting dashboard server...")

    if open_browser:
        def _open_browser():
            time.sleep(1.0)
            webbrowser.open(f"http://{HOST}:{PORT}")

        threading.Thread(target=_open_browser, daemon=True).start()

    serve(host=HOST, port=PORT)

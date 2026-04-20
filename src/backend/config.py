"""Backend configuration constants."""

import os
from pathlib import Path

DB_PATH = Path.home() / ".claude" / "usage.db"
HOST = os.environ.get("HOST", "localhost")
PORT = int(os.environ.get("PORT", "8082"))
MAX_CUSTOM_NAME_LENGTH = 80
EFFICIENCY_OUTPUT_INPUT_CAP = 4.0

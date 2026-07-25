"""Application configuration constants."""

from pathlib import Path

DB_PATH: Path = Path("data/xarchive.db")
PAGE_SIZE: int = 20
XURL_COMMAND: str = "xurl"
SYNC_TIMEOUT_SECONDS: int = 120
HOST: str = "127.0.0.1"
PORT: int = 8000

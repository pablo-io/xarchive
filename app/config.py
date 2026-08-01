"""Application configuration constants."""

from pathlib import Path

ROOT: Path = Path(__file__).resolve().parent.parent

DB_PATH: Path = ROOT / "data" / "xarchive.db"
PAGE_SIZE: int = 20
XURL_COMMAND: str = "xurl"
XURL_PAGE_SIZE: int = 5
SYNC_TIMEOUT_SECONDS: int = 120
SYNC_MIN_CREATED_AT: str = "2026-01-01T00:00:00Z"
HOST: str = "127.0.0.1"
PORT: int = 8000

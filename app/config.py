"""Application configuration constants."""

from pathlib import Path

ROOT: Path = Path(__file__).resolve().parent.parent

DB_PATH: Path = ROOT / "data" / "xarchive.db"
PAGE_SIZE: int = 20
XURL_COMMAND: str = "xurl"
SYNC_TIMEOUT_SECONDS: int = 120
HOST: str = "127.0.0.1"
PORT: int = 8000

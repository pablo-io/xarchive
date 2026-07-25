"""Pydantic models for xarchive data transfer and validation."""

from datetime import datetime

from pydantic import BaseModel


class XurlPostInput(BaseModel):
    """Validates the JSON output from `xurl likes` / `xurl bookmarks`."""

    id: str
    text: str
    author_id: str
    author_username: str
    author_name: str
    author_avatar: str
    created_at: str
    media_urls: list[str] = []
    url: str


class Post(BaseModel):
    """Read model for a post stored in the database. Used for templates and API."""

    id: str
    text: str
    author_id: str
    author_username: str
    author_name: str
    author_avatar: str
    created_at: str
    source: str
    media_urls: list[str] = []
    url: str
    imported_at: str

    @property
    def created_at_display(self) -> str:
        """Format the created_at ISO timestamp as 'Jan 15, 2025'."""
        try:
            dt = datetime.fromisoformat(self.created_at.replace("Z", "+00:00"))
            return dt.strftime("%b %d, %Y")
        except (ValueError, AttributeError):
            return self.created_at

    @property
    def is_like(self) -> bool:
        """True if this post was imported as a like."""
        return "like" in self.source

    @property
    def is_bookmark(self) -> bool:
        """True if this post was imported as a bookmark."""
        return "bookmark" in self.source

    @classmethod
    def from_db_row(cls, row: dict) -> "Post":
        """Create a Post from a database row dict (with media_urls already parsed)."""
        return cls(**row)


class SyncLog(BaseModel):
    """Tracks a single sync operation."""

    id: int | None = None
    source_type: str
    started_at: str
    finished_at: str | None = None
    status: str = "running"
    posts_new: int = 0
    posts_updated: int = 0
    error_message: str | None = None

"""Database layer: connection management, migrations, and CRUD helpers.

Uses raw SQL with parameterized queries. No ORM.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

import aiosqlite

from app.config import DB_PATH, PAGE_SIZE
from app.models import XurlPostInput

if TYPE_CHECKING:
    pass

# ── Module-level state ──────────────────────────────────────────────

_db: aiosqlite.Connection | None = None


# ── Migration definitions ───────────────────────────────────────────

_MIGRATIONS: list[str] = [
    """
    CREATE TABLE IF NOT EXISTS posts (
        id TEXT PRIMARY KEY,
        text TEXT NOT NULL,
        author_id TEXT NOT NULL,
        author_username TEXT NOT NULL,
        author_name TEXT NOT NULL,
        author_avatar TEXT NOT NULL,
        created_at TEXT NOT NULL,
        source TEXT NOT NULL,
        media_urls TEXT NOT NULL DEFAULT '[]',
        url TEXT NOT NULL,
        imported_at TEXT NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_posts_created_at ON posts(created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_posts_author_username ON posts(author_username)",
    "CREATE INDEX IF NOT EXISTS idx_posts_source ON posts(source)",
    """
    CREATE TABLE IF NOT EXISTS sync_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source_type TEXT NOT NULL,
        started_at TEXT NOT NULL,
        finished_at TEXT,
        status TEXT NOT NULL DEFAULT 'running',
        posts_new INTEGER NOT NULL DEFAULT 0,
        posts_updated INTEGER NOT NULL DEFAULT 0,
        error_message TEXT
    )
    """,
]

# ── Connection management ──────────────────────────────────────────


async def init_db() -> None:
    """Create the data directory, open the database connection, and run migrations."""
    global _db

    # Ensure the data directory exists
    data_dir = DB_PATH.parent
    Path(data_dir).mkdir(parents=True, exist_ok=True)

    # Connect to SQLite via aiosqlite
    _db = await aiosqlite.connect(str(DB_PATH))
    _db.row_factory = aiosqlite.Row

    # Enable WAL mode for better concurrent read performance
    await _db.execute("PRAGMA journal_mode=WAL")
    await _db.execute("PRAGMA foreign_keys=ON")

    # Run migrations
    for migration in _MIGRATIONS:
        await _db.execute(migration)

    await _db.commit()


async def close_db() -> None:
    """Close the database connection gracefully."""
    global _db
    if _db is not None:
        await _db.close()
        _db = None


async def get_db() -> aiosqlite.Connection:
    """Return the database connection, or raise if not initialized."""
    if _db is None:
        raise RuntimeError(
            "Database not initialized. Ensure init_db() is called during app startup."
        )
    return _db


# ── Post CRUD ───────────────────────────────────────────────────────


def _merge_source(existing: str, new: str) -> str:
    """Merge two source strings so a post can be both 'like' and 'bookmark'."""
    if existing == new:
        return existing
    parts: set[str] = set()
    for src in (existing, new):
        for part in src.split(","):
            parts.add(part.strip())
    return ",".join(sorted(parts))


async def upsert_post(post: XurlPostInput, source: str, now: str) -> str:
    """Insert or update a post in the database.

    Returns "new" if the post was inserted, "updated" if it was updated.
    Source merging: if a post is already a 'like' and we import it from
    bookmarks, the source becomes 'bookmark,like'.
    """
    db = await get_db()

    media_urls_json = json.dumps(post.media_urls)

    # Check if the post already exists to determine action and merge source
    cursor = await db.execute("SELECT source FROM posts WHERE id = ?", (post.id,))
    row = await cursor.fetchone()

    if row is None:
        # Insert
        await db.execute(
            """
            INSERT INTO posts (id, text, author_id, author_username, author_name,
                               author_avatar, created_at, source, media_urls, url, imported_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                post.id,
                post.text,
                post.author_id,
                post.author_username,
                post.author_name,
                post.author_avatar,
                post.created_at,
                source,
                media_urls_json,
                post.url,
                now,
            ),
        )
        await db.commit()
        return "new"

    # Update — merge source
    existing_source = row["source"]
    merged_source = _merge_source(existing_source, source)

    await db.execute(
        """
        INSERT INTO posts (id, text, author_id, author_username, author_name,
                           author_avatar, created_at, source, media_urls, url, imported_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            text = excluded.text,
            author_id = excluded.author_id,
            author_username = excluded.author_username,
            author_name = excluded.author_name,
            author_avatar = excluded.author_avatar,
            created_at = excluded.created_at,
            source = excluded.source,
            media_urls = excluded.media_urls,
            url = excluded.url,
            imported_at = excluded.imported_at
        """,
        (
            post.id,
            post.text,
            post.author_id,
            post.author_username,
            post.author_name,
            post.author_avatar,
            post.created_at,
            merged_source,
            media_urls_json,
            post.url,
            now,
        ),
    )
    await db.commit()
    return "updated"


def row_to_post_dict(row: aiosqlite.Row) -> dict:
    """Convert a database row to a dictionary suitable for Post.from_db_row()."""
    d = dict(row)
    # Parse media_urls from JSON string to list
    media_raw = d.get("media_urls", "[]")
    if isinstance(media_raw, str):
        try:
            d["media_urls"] = json.loads(media_raw)
        except (json.JSONDecodeError, TypeError):
            d["media_urls"] = []
    return d


async def get_posts(
    page: int = 1, per_page: int = PAGE_SIZE, source: str = "all"
) -> tuple[list[dict], int]:
    """Get paginated posts, optionally filtered by source.

    Returns (list_of_post_dicts, total_count).
    """
    return await search_posts(source=source, page=page, per_page=per_page)


def _build_post_query(
    q: str = "",
    username: str = "",
    date_from: str = "",
    date_to: str = "",
    source: str = "all",
) -> tuple[str, list]:
    """Build a parameterized WHERE clause and parameter list for post search.

    Returns (where_clause, params).
    """
    conditions: list[str] = []
    params: list = []

    if q:
        conditions.append("posts.text LIKE ?")
        params.append(f"%{q}%")

    if username:
        conditions.append("posts.author_username LIKE ?")
        params.append(f"%{username}%")

    if date_from:
        conditions.append("posts.created_at >= ?")
        params.append(f"{date_from}T00:00:00Z")

    if date_to:
        conditions.append("posts.created_at <= ?")
        params.append(f"{date_to}T23:59:59Z")

    if source != "all":
        conditions.append("posts.source LIKE ?")
        params.append(f"%{source}%")

    where = " AND ".join(conditions) if conditions else "1=1"
    return where, params


async def search_posts(
    q: str = "",
    username: str = "",
    date_from: str = "",
    date_to: str = "",
    source: str = "all",
    page: int = 1,
    per_page: int = PAGE_SIZE,
) -> tuple[list[dict], int]:
    """Search posts with dynamic filtering and pagination.

    Returns (list_of_post_dicts, total_count).
    All query parameters use parameterized queries — no string interpolation.
    """
    db = await get_db()
    where, params = _build_post_query(q, username, date_from, date_to, source)
    offset = (page - 1) * per_page

    # Count total matching rows
    count_sql = f"SELECT COUNT(*) as cnt FROM posts WHERE {where}"
    cursor = await db.execute(count_sql, params)
    row = await cursor.fetchone()
    total = row["cnt"] if row else 0

    # Fetch page of results
    data_sql = (
        f"SELECT * FROM posts WHERE {where}"
        f" ORDER BY created_at DESC LIMIT ? OFFSET ?"
    )
    cursor = await db.execute(data_sql, [*params, per_page, offset])
    rows = await cursor.fetchall()

    posts = [row_to_post_dict(r) for r in rows]
    return posts, total


# ── Sync log CRUD ───────────────────────────────────────────────────


async def create_sync_log(source_type: str) -> int:
    """Create a new sync_log entry and return its id."""
    db = await get_db()
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc).isoformat()
    cursor = await db.execute(
        """
        INSERT INTO sync_log (source_type, started_at, status)
        VALUES (?, ?, 'running')
        """,
        (source_type, now),
    )
    await db.commit()
    return cursor.lastrowid


async def update_sync_log(
    log_id: int,
    status: str,
    posts_new: int = 0,
    posts_updated: int = 0,
    error_message: str | None = None,
) -> None:
    """Update a sync_log entry with completion data."""
    db = await get_db()
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc).isoformat()
    await db.execute(
        """
        UPDATE sync_log
        SET finished_at = ?, status = ?, posts_new = ?, posts_updated = ?,
            error_message = ?
        WHERE id = ?
        """,
        (now, status, posts_new, posts_updated, error_message, log_id),
    )
    await db.commit()


async def get_last_sync_log() -> dict | None:
    """Return the most recent sync_log entry as a dict, or None if none exist."""
    db = await get_db()
    cursor = await db.execute(
        "SELECT * FROM sync_log ORDER BY id DESC LIMIT 1"
    )
    row = await cursor.fetchone()
    if row is None:
        return None
    return dict(row)

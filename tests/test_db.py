"""Tests for app.db — database layer (connection, migrations, CRUD)."""

import pytest

import app.db as db_module
from app.db import (
    create_sync_log,
    get_db,
    get_last_sync_log,
    get_posts,
    init_db,
    row_to_post_dict,
    search_posts,
    update_sync_log,
    upsert_post,
)
from app.models import XurlPostInput


# ── Helpers ──────────────────────────────────────────────────────────────


def _make_post(post_id: str = "p1", text: str = "hello", **kw) -> XurlPostInput:
    defaults = {
        "id": post_id,
        "text": text,
        "author_id": "u1",
        "author_username": "alice",
        "author_name": "Alice",
        "author_avatar": "https://example.com/a.jpg",
        "created_at": "2025-01-15T10:00:00Z",
        "media_urls": [],
        "url": "https://x.com/alice/status/1",
    }
    defaults.update(kw)
    return XurlPostInput(**defaults)


# ── init_db / get_db ────────────────────────────────────────────────────


async def test_init_db_creates_file(tmp_path, monkeypatch):
    """init_db creates the SQLite file on disk."""
    db_file = tmp_path / "fresh.db"
    monkeypatch.setattr("app.config.DB_PATH", db_file)
    monkeypatch.setattr("app.db.DB_PATH", db_file)

    assert not db_file.exists()
    await init_db()
    assert db_file.exists()

    await db_module.close_db()


async def test_init_db_twice(tmp_path, monkeypatch):
    """Calling init_db twice is safe (idempotent migrations)."""
    db_file = tmp_path / "double.db"
    monkeypatch.setattr("app.config.DB_PATH", db_file)
    monkeypatch.setattr("app.db.DB_PATH", db_file)

    await init_db()
    await init_db()  # must not raise

    await db_module.close_db()


async def test_get_db_before_init():
    """get_db raises RuntimeError when the DB has not been initialized."""
    original = db_module._db
    db_module._db = None
    try:
        with pytest.raises(RuntimeError, match="Database not initialized"):
            await get_db()
    finally:
        db_module._db = original


# ── upsert_post ──────────────────────────────────────────────────────────


async def test_upsert_post_new(test_db):
    """Inserting a brand-new post returns 'new' and the row exists."""
    post = _make_post("new_001", text="brand new post")
    result = await upsert_post(post, "like", "2025-01-01T00:00:00Z")

    assert result == "new"

    db = await get_db()
    cursor = await db.execute("SELECT * FROM posts WHERE id = ?", ("new_001",))
    row = await cursor.fetchone()
    assert row is not None
    assert row["text"] == "brand new post"
    assert row["source"] == "like"


async def test_upsert_post_update(test_db):
    """Upserting the same post id again returns 'updated'."""
    post_v1 = _make_post("upd_001", text="version 1")
    await upsert_post(post_v1, "like", "2025-01-01T00:00:00Z")

    post_v2 = _make_post("upd_001", text="version 2")
    result = await upsert_post(post_v2, "like", "2025-01-02T00:00:00Z")

    assert result == "updated"

    db = await get_db()
    cursor = await db.execute("SELECT text FROM posts WHERE id = ?", ("upd_001",))
    row = await cursor.fetchone()
    assert row["text"] == "version 2"


async def test_upsert_post_source_merge(test_db):
    """Insert as 'like', then 'bookmark' → source becomes 'bookmark,like'."""
    post = _make_post("merge_001", text="merge me")

    await upsert_post(post, "like", "2025-01-01T00:00:00Z")
    await upsert_post(post, "bookmark", "2025-01-02T00:00:00Z")

    db = await get_db()
    cursor = await db.execute("SELECT source FROM posts WHERE id = ?", ("merge_001",))
    row = await cursor.fetchone()
    assert row["source"] == "bookmark,like"


# ── get_posts / pagination / ordering ───────────────────────────────────


async def test_get_posts_pagination(sample_posts):
    """Page 1 returns first N posts, page 2 returns next N."""
    page1, total1 = await get_posts(page=1, per_page=5)
    assert len(page1) == 5
    assert total1 == 15

    page2, total2 = await get_posts(page=2, per_page=5)
    assert len(page2) == 5
    assert total2 == 15

    # Pages must not overlap
    ids1 = {p["id"] for p in page1}
    ids2 = {p["id"] for p in page2}
    assert ids1.isdisjoint(ids2)


async def test_get_posts_ordering(sample_posts):
    """Posts are ordered by created_at DESC."""
    posts, total = await get_posts(page=1, per_page=100)
    assert total == 15

    for i in range(len(posts) - 1):
        assert posts[i]["created_at"] >= posts[i + 1]["created_at"]


# ── search_posts ─────────────────────────────────────────────────────────


async def test_search_posts_text(sample_posts):
    """Text search is case-insensitive and matches substrings."""
    # "python" appears in topic for posts 0, 5, 10 (i % 5 == 0)
    posts, total = await search_posts(q="python")
    assert total >= 1
    for p in posts:
        assert "python" in p["text"].lower()

    # Case-insensitive: searching "Python" should yield same results
    posts_upper, total_upper = await search_posts(q="Python")
    assert total_upper == total


async def test_search_posts_username(sample_posts):
    """Search by username filters correctly."""
    posts, total = await search_posts(username="alice")
    assert total >= 1
    for p in posts:
        assert p["author_username"] == "alice"


async def test_search_posts_date_range(sample_posts):
    """Filter by date range returns posts within the range."""
    # Posts span roughly Nov 2024 – Jun 2025.
    # Filter for Jan 2025 only.
    posts, total = await search_posts(date_from="2025-01-01", date_to="2025-01-31")
    assert total >= 1
    for p in posts:
        # created_at looks like "2025-01-15T10:00:00Z"
        assert p["created_at"][:7] == "2025-01"


async def test_search_posts_source(sample_posts):
    """Filter by source returns only matching posts."""
    likes, total_likes = await search_posts(source="like")
    assert total_likes >= 1
    for p in likes:
        assert "like" in p["source"]

    bookmarks, total_bm = await search_posts(source="bookmark")
    assert total_bm >= 1
    for p in bookmarks:
        assert "bookmark" in p["source"]


async def test_search_posts_combined(sample_posts):
    """Combined filters apply AND logic."""
    posts, total = await search_posts(q="python", username="alice")
    for p in posts:
        assert "python" in p["text"].lower()
        assert p["author_username"] == "alice"


async def test_search_posts_empty(sample_posts):
    """No matching posts returns an empty list, not an error."""
    posts, total = await search_posts(q="zzz_nonexistent_term_zzz")
    assert posts == []
    assert total == 0


# ── sync_log CRUD ────────────────────────────────────────────────────────


async def test_create_sync_log(test_db):
    """create_sync_log inserts a row and returns its id."""
    log_id = await create_sync_log("likes")
    assert isinstance(log_id, int)
    assert log_id > 0

    db = await get_db()
    cursor = await db.execute("SELECT * FROM sync_log WHERE id = ?", (log_id,))
    row = await cursor.fetchone()
    assert row is not None
    assert row["source_type"] == "likes"
    assert row["status"] == "running"


async def test_update_sync_log(test_db):
    """update_sync_log changes status and counters."""
    log_id = await create_sync_log("bookmarks")
    await update_sync_log(log_id, "success", posts_new=5, posts_updated=2)

    db = await get_db()
    cursor = await db.execute("SELECT * FROM sync_log WHERE id = ?", (log_id,))
    row = await cursor.fetchone()
    assert row["status"] == "success"
    assert row["posts_new"] == 5
    assert row["posts_updated"] == 2
    assert row["finished_at"] is not None


async def test_get_last_sync_log(test_db):
    """get_last_sync_log returns the most recent entry."""
    await create_sync_log("likes")
    log_id_2 = await create_sync_log("bookmarks")

    last = await get_last_sync_log()
    assert last is not None
    assert last["id"] == log_id_2
    assert last["source_type"] == "bookmarks"


async def test_get_last_sync_log_empty(test_db):
    """get_last_sync_log returns None when the table is empty."""
    last = await get_last_sync_log()
    assert last is None


# ── row_to_post_dict ─────────────────────────────────────────────────────


async def test_row_to_post_dict(sample_posts):
    """row_to_post_dict parses media_urls from JSON string to list."""
    db = await get_db()

    # Fetch a post that has media (i % 4 == 0 → post_000, post_004, etc.)
    cursor = await db.execute("SELECT * FROM posts WHERE id = ?", ("post_0000",))
    row = await cursor.fetchone()
    assert row is not None

    d = row_to_post_dict(row)
    assert isinstance(d["media_urls"], list)
    assert len(d["media_urls"]) == 1
    assert d["media_urls"][0] == "https://example.com/media/0.jpg"

    # Fetch a post without media
    cursor2 = await db.execute("SELECT * FROM posts WHERE id = ?", ("post_0001",))
    row2 = await cursor2.fetchone()
    d2 = row_to_post_dict(row2)
    assert isinstance(d2["media_urls"], list)
    assert d2["media_urls"] == []

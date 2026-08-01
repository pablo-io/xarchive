"""Tests for app.routes.sync — sync trigger, pagination, cursor, and error handling."""

import pytest

import app.db as db_module
from app.db import get_db
from tests.conftest import MOCK_POSTS, MOCK_POSTS_PAGE_2


# ── POST /sync ───────────────────────────────────────────────────────────


async def test_sync_with_mock(app_client, mock_xurl):
    """POST /sync with mocked xurl inserts posts into the database."""
    response = await app_client.post("/sync")
    assert response.status_code == 200

    # Verify posts were inserted
    db = await get_db()
    cursor = await db.execute("SELECT COUNT(*) AS cnt FROM posts")
    row = await cursor.fetchone()
    assert row["cnt"] == len(MOCK_POSTS)

    # Verify a specific post
    cursor2 = await db.execute(
        "SELECT * FROM posts WHERE id = ?", ("mock_001",)
    )
    post_row = await cursor2.fetchone()
    assert post_row is not None
    assert post_row["source"] == "like"
    assert "Python" in post_row["text"]


async def test_sync_idempotent(app_client, mock_xurl):
    """Running sync twice produces no duplicates — cursor skips old posts."""
    # First sync
    resp1 = await app_client.post("/sync")
    assert resp1.status_code == 200

    db = await get_db()
    cursor = await db.execute("SELECT COUNT(*) AS cnt FROM posts")
    count_after_first = (await cursor.fetchone())["cnt"]
    assert count_after_first == len(MOCK_POSTS)

    # Second sync (same mock data) — posts are older than the cursor, so
    # nothing new should be inserted and nothing re-upserted.
    resp2 = await app_client.post("/sync")
    assert resp2.status_code == 200

    cursor2 = await db.execute("SELECT COUNT(*) AS cnt FROM posts")
    count_after_second = (await cursor2.fetchone())["cnt"]
    assert count_after_second == count_after_first

    # And no posts were re-imported (cursor stopped the pagination); the
    # success state is now an icon-only button with 0 new / 0 updated.
    assert 'aria-label="Sync again (0 new, 0 updated)"' in resp2.text


async def test_sync_returns_trigger_header(app_client, mock_xurl):
    """Successful sync response includes HX-Trigger: postsChanged header."""
    response = await app_client.post("/sync")
    assert response.status_code == 200
    assert response.headers.get("HX-Trigger") == "postsChanged"


async def test_sync_xurl_not_found(app_client, mock_xurl_not_found):
    """FileNotFoundError from xurl → error message rendered in response."""
    response = await app_client.post("/sync")
    assert response.status_code == 200
    # The error template should contain the error message
    assert "not found" in response.text.lower() or "error" in response.text.lower()


async def test_sync_incremental_skips_already_synced_posts(app_client, mock_xurl, test_db):
    """If the newest like is already in the DB, sync stops immediately."""
    from app.models import XurlPostInput

    # Seed the newest mock post — the first one the API would return.
    seed = dict(MOCK_POSTS[0])
    await db_module.upsert_post(XurlPostInput(**seed), "like", "2025-01-01T00:00:00Z")

    response = await app_client.post("/sync")
    assert response.status_code == 200

    db = await get_db()
    cursor = await db.execute("SELECT COUNT(*) AS cnt FROM posts")
    # Nothing new imported — the first like encountered was already synced.
    assert (await cursor.fetchone())["cnt"] == 1


# ── Pagination ───────────────────────────────────────────────────────────


async def test_sync_paginates_until_no_next_token(app_client, mock_xurl_paginated):
    """With two pages available, sync imports posts from both pages."""
    response = await app_client.post("/sync")
    assert response.status_code == 200

    db = await get_db()
    cursor = await db.execute("SELECT COUNT(*) AS cnt FROM posts")
    row = await cursor.fetchone()
    assert row["cnt"] == 2 * len(MOCK_POSTS)


async def test_sync_stops_at_first_synced_post(app_client, mock_xurl_paginated, test_db):
    """Once an already-synced post is found, pagination stops — no further
    pages are fetched."""
    from app.models import XurlPostInput

    # Seed the first post of page 2 (MOCK_POSTS_PAGE_2[0] == mock_101).
    # Page 1 (MOCK_POSTS) is all new and gets imported; page 2 starts with
    # an already-synced post, so sync stops there.
    seed = {
        "id": "mock_101",
        "text": "already synced",
        "author_id": "mock_user_6",
        "author_username": "mockuser6",
        "author_name": "Mock User Six",
        "author_avatar": "",
        "created_at": "2024-12-01T09:00:00Z",
        "media_urls": [],
        "url": "https://x.com/mockuser6/status/101",
    }
    await db_module.upsert_post(XurlPostInput(**seed), "like", "2025-01-01T00:00:00Z")

    response = await app_client.post("/sync")
    assert response.status_code == 200

    db = await get_db()
    cursor = await db.execute("SELECT COUNT(*) AS cnt FROM posts")
    # Page 1 (5 posts) imported + the seed = 6. Page 2 was not imported.
    assert (await cursor.fetchone())["cnt"] == len(MOCK_POSTS) + 1

    # Only /2/users/me + page 1 + page 2 (which hits the seed) = 3 calls.
    assert mock_xurl_paginated.call_count == 3


# ── GET /sync/status ─────────────────────────────────────────────────────


async def test_sync_status_idle(app_client):
    """GET /sync/status returns idle state when no sync has run."""
    response = await app_client.get("/sync/status")
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")


# ── GET /api/sync/status ─────────────────────────────────────────────────


async def test_sync_api_status_never_synced(app_client):
    """GET /api/sync/status returns 'never' when no sync has been performed."""
    response = await app_client.get("/api/sync/status")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "never"


async def test_sync_api_status_after_sync(app_client, mock_xurl):
    """GET /api/sync/status returns sync info after a sync has run."""
    # Run a sync first
    await app_client.post("/sync")

    response = await app_client.get("/api/sync/status")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["source_type"] == "likes"
    assert data["posts_new"] == len(MOCK_POSTS)
    assert "started_at" in data
    assert "finished_at" in data


# ── Rate limit / resume ──────────────────────────────────────────────────


async def test_sync_rate_limited_persists_token(app_client, mock_xurl_rate_limited):
    """On 429, sync stops, reports the error, and saves the pagination token."""
    response = await app_client.post("/sync")
    assert response.status_code == 200
    assert "rate limit" in response.text.lower()

    db = await get_db()
    cursor = await db.execute("SELECT next_token FROM sync_log ORDER BY id DESC LIMIT 1")
    row = await cursor.fetchone()
    # Token from the successful page is persisted for resume.
    assert row["next_token"] == "token_next"

    # Page 1 posts were still imported before the rate limit hit.
    cursor2 = await db.execute("SELECT COUNT(*) AS cnt FROM posts")
    assert (await cursor2.fetchone())["cnt"] == len(MOCK_POSTS)


async def test_sync_resumes_from_saved_token(app_client, mock_xurl_paginated, test_db):
    """A sync after a rate-limit resumes from the persisted token."""
    from app.db import save_sync_token

    # Simulate a previous rate-limited sync that saved a token.
    log_id = await db_module.create_sync_log("likes")
    await save_sync_token(log_id, "token_next", "incremental")
    await db_module.update_sync_log(log_id, "error", error_message="Rate limit reached")

    # mock_xurl_paginated returns page 1 (with token) then page 2.
    # Resuming from "token_next" starts at page 2, so only page 2 is imported.
    response = await app_client.post("/sync")
    assert response.status_code == 200

    db = await get_db()
    cursor = await db.execute("SELECT COUNT(*) AS cnt FROM posts")
    assert (await cursor.fetchone())["cnt"] == len(MOCK_POSTS_PAGE_2)

    # The resume token was cleared after successful completion.
    cursor2 = await db.execute("SELECT next_token FROM sync_log ORDER BY id DESC LIMIT 1")
    row = await cursor2.fetchone()
    assert row["next_token"] is None


# ── 2026 cutoff ──────────────────────────────────────────────────────────


async def test_sync_stops_at_2026_cutoff(app_client, test_db):
    """Posts created before 2026 stop the sync and are not imported."""
    import json
    from unittest.mock import AsyncMock, MagicMock, patch

    old_posts = [
        {
            "id": "old_001",
            "text": "pre-2026 post",
            "author_id": "u_old",
            "created_at": "2025-12-31T23:59:59Z",
            "author_username": "olduser",
            "author_name": "Old User",
            "author_avatar": "https://example.com/old.jpg",
        },
        {
            "id": "new_001",
            "text": "2026 post",
            "author_id": "u_new",
            "created_at": "2026-06-01T12:00:00Z",
            "author_username": "newuser",
            "author_name": "New User",
            "author_avatar": "https://example.com/new.jpg",
        },
    ]

    async def _exec(*args, **kwargs):
        path = args[1]
        if "/2/users/me" in path:
            return MagicMock(
                communicate=AsyncMock(return_value=(json.dumps({"data": {"id": "1", "username": "me"}}).encode(), b"")),
                returncode=0,
            )
        return MagicMock(
            communicate=AsyncMock(
                return_value=(
                    json.dumps({"data": old_posts, "includes": {"users": []}, "meta": {}}).encode(),
                    b"",
                )
            ),
            returncode=0,
        )

    with patch("asyncio.create_subprocess_exec", side_effect=_exec):
        response = await app_client.post("/sync")
    assert response.status_code == 200

    db = await get_db()
    cursor = await db.execute("SELECT COUNT(*) AS cnt FROM posts")
    assert (await cursor.fetchone())["cnt"] == 0


# ── like_order ───────────────────────────────────────────────────────────


async def test_sync_assigns_like_order(app_client, mock_xurl):
    """Imported posts get like_order so the newest like sorts first."""
    await app_client.post("/sync")

    db = await get_db()
    cursor = await db.execute("SELECT id, like_order FROM posts ORDER BY like_order DESC")
    rows = await cursor.fetchall()
    assert len(rows) == len(MOCK_POSTS)

    # All posts got distinct like_orders.
    orders = [r["like_order"] for r in rows]
    assert len(set(orders)) == len(orders)
    # First (highest like_order) is the newest like in the API response order.
    # MOCK_POSTS[0] is the most recent like.
    assert rows[0]["id"] == MOCK_POSTS[0]["id"]

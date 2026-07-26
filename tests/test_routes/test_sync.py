"""Tests for app.routes.sync — sync trigger, status, and xurl subprocess mocking."""

import pytest

import app.db as db_module
from app.db import get_db
from tests.conftest import MOCK_POSTS


# ── POST /sync ───────────────────────────────────────────────────────────


async def test_sync_with_mock(app_client, mock_xurl):
    """POST /sync with mocked xurl inserts posts into the database."""
    response = await app_client.post("/sync", data={"source_type": "likes"})
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
    assert post_row["source"] == "likes"  # sync stores "likes"/"bookmarks" (plural)
    assert "Python" in post_row["text"]


async def test_sync_idempotent(app_client, mock_xurl):
    """Running sync twice produces no duplicates — upsert merges on id."""
    # First sync
    resp1 = await app_client.post("/sync", data={"source_type": "likes"})
    assert resp1.status_code == 200

    db = await get_db()
    cursor = await db.execute("SELECT COUNT(*) AS cnt FROM posts")
    count_after_first = (await cursor.fetchone())["cnt"]
    assert count_after_first == len(MOCK_POSTS)

    # Second sync (same mock data)
    resp2 = await app_client.post("/sync", data={"source_type": "likes"})
    assert resp2.status_code == 200

    cursor2 = await db.execute("SELECT COUNT(*) AS cnt FROM posts")
    count_after_second = (await cursor2.fetchone())["cnt"]
    # No duplicates — same count
    assert count_after_second == count_after_first


async def test_sync_returns_trigger_header(app_client, mock_xurl):
    """Successful sync response includes HX-Trigger: postsChanged header."""
    response = await app_client.post("/sync", data={"source_type": "likes"})
    assert response.status_code == 200
    assert response.headers.get("HX-Trigger") == "postsChanged"


async def test_sync_xurl_not_found(app_client, mock_xurl_not_found):
    """FileNotFoundError from xurl → error message rendered in response."""
    response = await app_client.post("/sync", data={"source_type": "likes"})
    assert response.status_code == 200
    # The error template should contain the error message
    assert "not found" in response.text.lower() or "error" in response.text.lower()


async def test_sync_both_sources(app_client, mock_xurl):
    """POST /sync with source_type=both syncs likes and bookmarks."""
    response = await app_client.post("/sync", data={"source_type": "both"})
    assert response.status_code == 200
    # mock_xurl is called twice (once for likes, once for bookmarks)
    assert mock_xurl.call_count == 2


async def test_sync_invalid_source(app_client):
    """POST /sync with invalid source_type returns an error."""
    response = await app_client.post("/sync", data={"source_type": "invalid"})
    assert response.status_code == 200
    assert "invalid" in response.text.lower() or "error" in response.text.lower()


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
    await app_client.post("/sync", data={"source_type": "likes"})

    response = await app_client.get("/api/sync/status")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["source_type"] == "likes"
    assert data["posts_new"] == len(MOCK_POSTS)
    assert "started_at" in data
    assert "finished_at" in data

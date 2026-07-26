"""Shared test fixtures for xarchive."""

import asyncio
import json
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import app.db as db_module
from app.models import XurlPostInput


# ---------------------------------------------------------------------------
# Database fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def test_db(tmp_path, monkeypatch):
    """Create a temporary SQLite database for testing.

    Patches DB_PATH in both config and db modules so that init_db()
    creates the file inside *tmp_path* instead of data/xarchive.db.
    Yields the aiosqlite connection; closes it on teardown.
    """
    db_file = tmp_path / "test_xarchive.db"

    # Patch DB_PATH in both modules (config is the source, db imports it)
    monkeypatch.setattr("app.config.DB_PATH", db_file)
    monkeypatch.setattr("app.db.DB_PATH", db_file)

    await db_module.init_db()
    yield db_module._db
    await db_module.close_db()


# ---------------------------------------------------------------------------
# Sync-state reset (autouse — runs for every test)
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
async def _reset_sync_state():
    """Reset sync module-level state between tests."""
    from app.routes import sync as sync_module

    sync_module._sync_in_progress = False
    sync_module._last_sync_result = None
    sync_module._sync_lock = asyncio.Lock()
    yield


# ---------------------------------------------------------------------------
# HTTP client fixture
# ---------------------------------------------------------------------------


@pytest.fixture
async def app_client(test_db):
    """httpx.AsyncClient wired to a FastAPI app that uses the test DB.

    The app is created *without* the production lifespan so that init_db()
    is not called a second time (the test_db fixture already did that).
    """
    from httpx import ASGITransport, AsyncClient

    from fastapi import FastAPI
    from fastapi.staticfiles import StaticFiles

    from app.config import ROOT
    from app.routes import posts, sync

    app = FastAPI(title="xarchive-test")

    static_dir = ROOT / "app" / "static"
    static_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    app.include_router(posts.router)
    app.include_router(sync.router)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


# ---------------------------------------------------------------------------
# Sample data
# ---------------------------------------------------------------------------


@pytest.fixture
async def sample_posts(test_db):
    """Insert 15 sample posts with varied text, usernames, dates, sources, media.

    Posts are spread across ~225 days (roughly Nov 2024 – Jun 2025).
    Sources cycle between 'like' and 'bookmark'; every 4th post has media.
    """
    now = datetime.now(timezone.utc).isoformat()

    usernames = ["alice", "bob", "charlie", "diana", "eve"]
    topics = ["python", "testing", "rust", "webdev", "machine learning"]

    inserted: list[dict] = []

    for i in range(15):
        days_ago = i * 15
        dt = datetime(2025, 6, 1, tzinfo=timezone.utc) - timedelta(days=days_ago)
        created_at = dt.strftime("%Y-%m-%dT%H:%M:%SZ")

        source = "bookmark" if i % 3 == 0 else "like"
        has_media = i % 4 == 0
        username = usernames[i % 5]
        topic = topics[i % 5]

        post_data = {
            "id": f"post_{i:04d}",
            "text": f"Sample post {i} about {topic} from {username}",
            "author_id": f"user_{i % 5}",
            "author_username": username,
            "author_name": f"User {username.capitalize()}",
            "author_avatar": f"https://example.com/avatar/{username}.jpg",
            "created_at": created_at,
            "media_urls": [f"https://example.com/media/{i}.jpg"] if has_media else [],
            "url": f"https://x.com/{username}/status/{1000 + i}",
        }

        post_input = XurlPostInput(**post_data)
        await db_module.upsert_post(post_input, source, now)
        inserted.append(post_data)

    return inserted


# ---------------------------------------------------------------------------
# Mock xurl subprocess helpers
# ---------------------------------------------------------------------------

MOCK_POSTS: list[dict] = [
    {
        "id": "mock_001",
        "text": "Mock post about Python programming",
        "author_id": "mock_user_1",
        "author_username": "mockuser1",
        "author_name": "Mock User One",
        "author_avatar": "https://example.com/mock1.jpg",
        "created_at": "2025-01-15T10:00:00Z",
        "media_urls": [],
        "url": "https://x.com/mockuser1/status/1",
    },
    {
        "id": "mock_002",
        "text": "Another mock post about testing",
        "author_id": "mock_user_2",
        "author_username": "mockuser2",
        "author_name": "Mock User Two",
        "author_avatar": "https://example.com/mock2.jpg",
        "created_at": "2025-02-20T14:30:00Z",
        "media_urls": ["https://example.com/mock_media.jpg"],
        "url": "https://x.com/mockuser2/status/2",
    },
    {
        "id": "mock_003",
        "text": "Third mock about Rust and webdev",
        "author_id": "mock_user_3",
        "author_username": "mockuser3",
        "author_name": "Mock User Three",
        "author_avatar": "https://example.com/mock3.jpg",
        "created_at": "2025-03-10T08:15:00Z",
        "media_urls": [],
        "url": "https://x.com/mockuser3/status/3",
    },
    {
        "id": "mock_004",
        "text": "Fourth mock about AI and python",
        "author_id": "mock_user_4",
        "author_username": "mockuser4",
        "author_name": "Mock User Four",
        "author_avatar": "https://example.com/mock4.jpg",
        "created_at": "2025-04-05T16:45:00Z",
        "media_urls": [
            "https://example.com/mock_media_a.jpg",
            "https://example.com/mock_media_b.jpg",
        ],
        "url": "https://x.com/mockuser4/status/4",
    },
    {
        "id": "mock_005",
        "text": "Fifth mock about web development",
        "author_id": "mock_user_5",
        "author_username": "mockuser5",
        "author_name": "Mock User Five",
        "author_avatar": "https://example.com/mock5.jpg",
        "created_at": "2025-05-12T09:00:00Z",
        "media_urls": [],
        "url": "https://x.com/mockuser5/status/5",
    },
]


def _make_mock_process(posts_json: list[dict]) -> MagicMock:
    """Build a mock asyncio subprocess that returns *posts_json* as stdout."""
    proc = MagicMock()
    proc.communicate = AsyncMock(
        return_value=(json.dumps(posts_json).encode("utf-8"), b""),
    )
    proc.returncode = 0
    proc.kill = MagicMock()
    proc.wait = AsyncMock()
    return proc


@pytest.fixture
def mock_xurl():
    """Patch ``asyncio.create_subprocess_exec`` to return 5 canned posts."""
    proc = _make_mock_process(MOCK_POSTS)
    mock_exec = AsyncMock(return_value=proc)

    with patch("asyncio.create_subprocess_exec", mock_exec) as m:
        yield m


@pytest.fixture
def mock_xurl_not_found():
    """Patch ``asyncio.create_subprocess_exec`` to raise FileNotFoundError."""
    with patch(
        "asyncio.create_subprocess_exec",
        side_effect=FileNotFoundError("xurl not found"),
    ) as m:
        yield m

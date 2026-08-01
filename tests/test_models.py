"""Tests for app.models — Pydantic models and their properties."""

import pytest
from pydantic import ValidationError

from app.models import Post, SyncLog, XurlPostInput


# ── XurlPostInput ────────────────────────────────────────────────────────


def test_xurl_post_input_valid():
    """Valid data passes validation without errors."""
    data = {
        "id": "12345",
        "text": "Hello world",
        "author_id": "u1",
        "author_username": "alice",
        "author_name": "Alice",
        "author_avatar": "https://example.com/avatar.jpg",
        "created_at": "2025-01-15T10:00:00Z",
        "media_urls": ["https://example.com/img.jpg"],
        "url": "https://x.com/alice/status/12345",
    }
    post = XurlPostInput.model_validate(data)
    assert post.id == "12345"
    assert post.text == "Hello world"
    assert post.media_urls == ["https://example.com/img.jpg"]


def test_xurl_post_input_missing_field():
    """Missing a required field raises ValidationError."""
    data = {
        "id": "12345",
        # "text" is missing
        "author_id": "u1",
        "author_username": "alice",
        "author_name": "Alice",
        "author_avatar": "https://example.com/avatar.jpg",
        "created_at": "2025-01-15T10:00:00Z",
        "url": "https://x.com/alice/status/12345",
    }
    with pytest.raises(ValidationError):
        XurlPostInput.model_validate(data)


def test_xurl_post_input_default_media_urls():
    """media_urls defaults to an empty list when omitted."""
    data = {
        "id": "12345",
        "text": "Hello",
        "author_id": "u1",
        "author_username": "alice",
        "author_name": "Alice",
        "author_avatar": "https://example.com/a.jpg",
        "created_at": "2025-01-15T10:00:00Z",
        "url": "https://x.com/alice/status/1",
    }
    post = XurlPostInput.model_validate(data)
    assert post.media_urls == []


# ── Post ─────────────────────────────────────────────────────────────────


def _make_post(**overrides) -> Post:
    defaults = {
        "id": "1",
        "text": "test",
        "author_id": "u1",
        "author_username": "alice",
        "author_name": "Alice",
        "author_avatar": "https://example.com/a.jpg",
        "created_at": "2025-01-15T10:00:00Z",
        "source": "like",
        "media_urls": [],
        "url": "https://x.com/alice/status/1",
        "imported_at": "2025-06-01T00:00:00Z",
    }
    defaults.update(overrides)
    return Post(**defaults)


def test_post_created_at_display():
    """created_at_display formats ISO timestamp as 'Jan 15, 2025'."""
    post = _make_post(created_at="2025-01-15T10:30:00Z")
    assert post.created_at_display == "Jan 15, 2025"


def test_post_created_at_display_december():
    """created_at_display handles month names correctly."""
    post = _make_post(created_at="2024-12-25T08:00:00Z")
    assert post.created_at_display == "Dec 25, 2024"


def test_post_created_at_display_invalid():
    """created_at_display falls back to raw string on parse failure."""
    post = _make_post(created_at="not-a-date")
    assert post.created_at_display == "not-a-date"


def test_post_is_like():
    """is_like returns True when source contains 'like'."""
    assert _make_post(source="like").is_like is True
    assert _make_post(source="like,bookmark").is_like is True
    assert _make_post(source="bookmark").is_like is False


def test_post_text_html_linkifies_urls():
    """text_html escapes HTML and wraps URLs in clickable anchors."""
    post = _make_post(text='Check https://example.com/a?b=1&c=2 now')
    out = post.text_html
    assert "https://example.com/a?b=1&amp;c=2" in out
    assert '<a href="https://example.com/a?b=1&amp;c=2"' in out
    assert 'target="_blank"' in out
    assert 'rel="noopener noreferrer"' in out


def test_post_text_html_escapes_html():
    """text_html escapes <script> tags so they are not injected."""
    post = _make_post(text='<script>alert("x")</script> & more')
    out = post.text_html
    assert "<script>" not in out
    assert "&lt;script&gt;" in out
    assert "&amp; more" in out


def test_post_text_html_keeps_plain_text():
    """text_html leaves text without URLs untouched (escaped)."""
    post = _make_post(text="hello world, no links")
    assert post.text_html == "hello world, no links"


def test_post_from_db_row():
    """from_db_row creates a Post from a dict (e.g., parsed DB row)."""
    row = {
        "id": "42",
        "text": "from db",
        "author_id": "u2",
        "author_username": "bob",
        "author_name": "Bob",
        "author_avatar": "https://example.com/b.jpg",
        "created_at": "2025-03-01T12:00:00Z",
        "source": "bookmark",
        "media_urls": ["https://example.com/img.jpg"],
        "url": "https://x.com/bob/status/42",
        "imported_at": "2025-06-01T00:00:00Z",
    }
    post = Post.from_db_row(row)
    assert post.id == "42"
    assert post.text == "from db"
    assert post.media_urls == ["https://example.com/img.jpg"]


# ── SyncLog ──────────────────────────────────────────────────────────────


def test_sync_log_default_values():
    """SyncLog has correct defaults for optional fields."""
    log = SyncLog(source_type="likes", started_at="2025-06-01T00:00:00Z")
    assert log.status == "running"
    assert log.posts_new == 0
    assert log.posts_updated == 0
    assert log.finished_at is None
    assert log.error_message is None
    assert log.id is None


def test_sync_log_full():
    """SyncLog accepts all fields."""
    log = SyncLog(
        id=1,
        source_type="bookmarks",
        started_at="2025-06-01T00:00:00Z",
        finished_at="2025-06-01T00:01:00Z",
        status="success",
        posts_new=10,
        posts_updated=3,
        error_message=None,
    )
    assert log.id == 1
    assert log.status == "success"
    assert log.posts_new == 10
    assert log.posts_updated == 3

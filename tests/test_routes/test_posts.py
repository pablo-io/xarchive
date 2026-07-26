"""Tests for app.routes.posts — post listing, search, pagination routes."""

import pytest


# ── GET / ────────────────────────────────────────────────────────────────


async def test_index(app_client):
    """GET / returns 200 with a full HTML page."""
    response = await app_client.get("/")
    assert response.status_code == 200
    content_type = response.headers.get("content-type", "")
    assert "text/html" in content_type
    # Must contain the HTML shell
    assert "<html" in response.text
    assert "xarchive" in response.text


async def test_index_contains_htmx(app_client):
    """The index page includes the HTMX CDN script."""
    response = await app_client.get("/")
    assert "htmx" in response.text.lower()


# ── GET /posts ───────────────────────────────────────────────────────────


async def test_list_posts_returns_html(app_client, sample_posts):
    """GET /posts returns an HTML fragment with post cards."""
    response = await app_client.get("/posts")
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")
    # Should contain at least one post card (<article> tag)
    assert "<article" in response.text


async def test_list_posts_empty_db(app_client):
    """Empty DB returns 200 with a friendly empty-state message (not 404)."""
    response = await app_client.get("/posts")
    assert response.status_code == 200
    assert "No posts found" in response.text


async def test_list_posts_search(app_client, sample_posts):
    """GET /posts?q=python filters results to matching posts."""
    response = await app_client.get("/posts", params={"q": "python"})
    assert response.status_code == 200
    # All visible post texts should contain "python" (case-insensitive)
    assert "python" in response.text.lower()


async def test_list_posts_search_by_username(app_client, sample_posts):
    """GET /posts?username=alice filters by author."""
    response = await app_client.get("/posts", params={"username": "alice"})
    assert response.status_code == 200
    assert "alice" in response.text.lower()


async def test_list_posts_pagination(app_client, sample_posts):
    """GET /posts?page=2 returns page 2 (may be empty with 15 posts / PAGE_SIZE=20)."""
    response = await app_client.get("/posts", params={"page": 2})
    assert response.status_code == 200
    # The response is valid HTML even if no posts are on this page
    assert "text/html" in response.headers.get("content-type", "")


async def test_list_posts_source_filter(app_client, sample_posts):
    """GET /posts?source=like returns only like posts."""
    response = await app_client.get("/posts", params={"source": "like"})
    assert response.status_code == 200
    # The response should contain the like badge
    assert "like" in response.text.lower()


# ── GET /posts/load-more ─────────────────────────────────────────────────


async def test_load_more(app_client, sample_posts):
    """GET /posts/load-more?page=1 returns a cards-only HTML fragment."""
    response = await app_client.get("/posts/load-more", params={"page": 1})
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")
    # Should contain post cards (<article> tags)
    assert "<article" in response.text


async def test_load_more_page_2(app_client, sample_posts):
    """GET /posts/load-more?page=2 returns 200 even if no posts remain."""
    response = await app_client.get("/posts/load-more", params={"page": 2})
    assert response.status_code == 200


# ── GET /api/posts ───────────────────────────────────────────────────────


async def test_api_list_posts(app_client, sample_posts):
    """GET /api/posts returns valid JSON with posts array and pagination info."""
    response = await app_client.get("/api/posts")
    assert response.status_code == 200
    assert "application/json" in response.headers.get("content-type", "")

    data = response.json()
    assert "posts" in data
    assert "total" in data
    assert "page" in data
    assert "per_page" in data
    assert isinstance(data["posts"], list)
    assert data["total"] == 15
    assert data["page"] == 1


async def test_api_list_posts_empty(app_client):
    """GET /api/posts with empty DB returns empty posts list."""
    response = await app_client.get("/api/posts")
    assert response.status_code == 200
    data = response.json()
    assert data["posts"] == []
    assert data["total"] == 0


async def test_api_list_posts_search(app_client, sample_posts):
    """GET /api/posts?q=python filters JSON results."""
    response = await app_client.get("/api/posts", params={"q": "python"})
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    for post in data["posts"]:
        assert "python" in post["text"].lower()

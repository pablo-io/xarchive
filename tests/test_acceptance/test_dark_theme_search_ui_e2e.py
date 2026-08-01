"""End-to-end acceptance tests for the dark-theme-search-ui feature.

These tests verify the acceptance criteria from
``docs/spec/dark-theme-search-ui.md`` at the HTTP/route boundary. They cross
the route -> template -> CSS/JS boundary to confirm that each criterion of
the spec is satisfied when the page is rendered through the real FastAPI
app.

They complement (do not duplicate) the existing tests:

- Unit tests in ``test_frontend/`` render individual templates in isolation
  and assert specific markup pieces (one template at a time).
- Unit tests in ``test_routes/`` exercise the routes for basic happy paths
  (one route at a time, mostly happy-path).
- Unit tests in ``tests/js/test_ui_logic.mjs`` exercise the inline JS in a
  Node ``vm`` sandbox (no HTTP, no real template).

This file provides the integration/acceptance layer that ties the above
pieces together: the rendered page, accessed through the real HTTP
endpoints, must satisfy the spec.

Every test below is mapped to a specific acceptance criterion in the spec.
Tests that fail are findings (spec violations), not test bugs to paper over.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

import app.db as db_module
from app.models import XurlPostInput


CSS_PATH = (
    Path(__file__).resolve().parents[2]
    / "app"
    / "static"
    / "css"
    / "custom.css"
)


# ── Helpers ───────────────────────────────────────────────────────────────


def _read_css() -> str:
    return CSS_PATH.read_text(encoding="utf-8")


async def _insert_post(
    post_id: str,
    text: str,
    created_at: str,
    media_urls: list[str],
    source: str = "like",
) -> None:
    """Insert a single post directly through the DB layer (no HTTP)."""
    post_data = {
        "id": post_id,
        "text": text,
        "author_id": "u1",
        "author_username": "alice",
        "author_name": "Alice",
        "author_avatar": "",
        "created_at": created_at,
        "media_urls": media_urls,
        "url": f"https://x.com/alice/status/{post_id}",
    }
    await db_module.upsert_post(
        XurlPostInput(**post_data),
        source,
        datetime.now(timezone.utc).isoformat(),
    )


# ── RF-1: dark theme system — page-level integration ──────────────────────


async def test_get_index_includes_theme_toggle_button(app_client):
    """RF-1 acceptance: the page header has a theme toggle button with the
    correct ARIA label and ``onclick="toggleTheme()"`` handler (per
    ``docs/spec/dark-theme-search-ui.md`` RF-1).
    """
    response = await app_client.get("/")
    assert response.status_code == 200
    body = response.text
    assert 'id="theme-toggle"' in body
    assert 'onclick="toggleTheme()"' in body
    assert 'aria-label="Toggle dark theme"' in body


async def test_get_index_includes_theme_javascript(app_client):
    """RF-1 acceptance: the theme JS is embedded in the page and uses the
    ``xarchive-theme`` localStorage key for persistence (per the spec's
    persistence requirement).
    """
    response = await app_client.get("/")
    body = response.text
    assert "function toggleTheme" in body
    assert "xarchive-theme" in body
    assert "localStorage" in body


def test_dark_theme_css_uses_exact_x_com_palette():
    """RF-1 acceptance: the dark theme CSS defines the EXACT x.com palette
    from the spec (background #000000, card #16181c, text #e7e9ea,
    secondary #71767b, border #2f3336, accent #1d9bf0, hover #181818).
    """
    css = _read_css()
    assert '[data-theme="dark"]' in css
    expected = {
        "--bg-page": "#000000",
        "--bg-card": "#16181c",
        "--text-primary": "#e7e9ea",
        "--text-secondary": "#71767b",
        "--border-color": "#2f3336",
        "--accent-color": "#1d9bf0",
        "--bg-hover": "#181818",
    }
    for var, value in expected.items():
        assert f"{var}: {value}" in css, f"dark theme missing {var}: {value}"


# ── RF-2: sync button at the page level — combobox removed ────────────────


async def test_get_sync_status_idle_has_no_select_combobox(app_client):
    """RF-2 acceptance: GET ``/sync/status`` in idle state has no ``<select>``
    combobox for the source filter (the old duplicate has been removed —
    the spec says the Sync button should be a simple button, not a button
    plus combobox).
    """
    response = await app_client.get("/sync/status")
    assert response.status_code == 200
    body = response.text.lower()
    assert "<select" not in body
    # The "All / Likes / Bookmarks" option set must also be gone.
    assert "all sources" not in body
    assert "likes</option" not in body
    assert "bookmarks</option" not in body


async def test_get_sync_status_idle_submits_direct_post(app_client):
    """RF-2 acceptance: the idle sync button submits a direct HTMX POST to
    ``/sync`` with no ``source_type`` selector (only likes are synced now).
    """
    response = await app_client.get("/sync/status")
    body = response.text
    assert 'hx-post="/sync"' in body
    assert 'name="source_type"' not in body
    assert 'aria-label="Sync likes"' in body


async def test_get_index_header_has_no_select_combobox(app_client):
    """RF-2 acceptance: the rendered page's ``<header>`` section contains no
    ``<select>`` element. (The ``<select>`` for the source filter lives in
    the search bar — not in the top bar.) This is the end-to-end check
    that complements the template-level tests in ``test_sync_button.py``.
    """
    response = await app_client.get("/")
    body = response.text
    header_start = body.index("<header")
    header_end = body.index("</header>") + len("</header>")
    header = body[header_start:header_end]
    assert "<select" not in header.lower()


# ── RF-3: search-bar visibility at the page level ─────────────────────────


async def test_get_index_search_bar_is_hidden_by_default(app_client):
    """RF-3 acceptance: GET ``/`` renders the search bar with the ``hidden``
    class by default (no auto-show without URL params).
    """
    response = await app_client.get("/")
    body = response.text
    assert 'id="search-bar-wrapper"' in body
    assert "search-bar-wrapper hidden" in body


async def test_get_index_includes_search_toggle_handler(app_client):
    """RF-3 acceptance: the search toggle button is wired to
    ``toggleSearchBar()`` and has the correct ARIA label.
    """
    response = await app_client.get("/")
    body = response.text
    assert 'id="search-toggle"' in body
    assert 'onclick="toggleSearchBar()"' in body
    assert 'aria-label="Toggle search bar"' in body


async def test_get_index_includes_has_search_params_helper(app_client):
    """RF-3 acceptance: the page contains the ``hasSearchParams()`` helper
    that auto-shows the bar when the URL has any of ``q``, ``username``,
    ``date_from`` or ``date_to`` (per the spec's auto-show requirement).
    The ``source`` key has been removed with the source filter.
    """
    response = await app_client.get("/")
    body = response.text
    assert "function hasSearchParams" in body
    # The recognised parameter keys must match the spec exactly.
    for key in ("q", "username", "date_from", "date_to"):
        assert key in body, f"hasSearchParams does not check for {key!r}"
    # The source filter was removed, so 'source' must not be recognised.
    func_start = body.index("function hasSearchParams")
    func_end = body.index("}", func_start)
    assert "'source'" not in body[func_start:func_end]


# ── RF-4: compact date fields + end-to-end date filter via HTTP ───────────


async def test_get_index_search_bar_renders_compact_date_labels(app_client):
    """RF-4 acceptance: the search form has compact date labels with the
    default ``Inicio`` / ``Fin`` text. Real ``type="date"`` inputs must be
    present (visually hidden but functional for HTMX submission).
    """
    response = await app_client.get("/")
    body = response.text
    assert 'id="label-date-from"' in body
    assert 'id="label-date-to"' in body
    assert "Inicio" in body
    assert "Fin" in body
    assert 'name="date_from"' in body
    assert 'name="date_to"' in body
    assert 'type="date"' in body


async def test_get_posts_filter_by_date_from(app_client, sample_posts):
    """RF-4 acceptance: GET ``/posts?date_from=YYYY-MM-DD`` filters the post
    list end-to-end (route -> DB -> template). Sample posts are spread
    across ~225 days; a ``date_from`` of ``2025-05-01`` must keep posts on
    or after that date and exclude earlier ones.

    This is a real gap in the existing suite: the DB layer has
    ``test_search_posts_date_range`` and the HTTP layer has tests for
    ``q`` and ``username`` filters, but no HTTP-level test for
    ``date_from`` / ``date_to``.
    """
    response = await app_client.get(
        "/posts", params={"date_from": "2025-05-01"}
    )
    assert response.status_code == 200
    body = response.text.lower()
    # post_000 (2025-06-01) must be present.
    assert "post 0 about" in body
    # post_003 (2025-04-17) and post_005 (2025-03-18) must NOT be present.
    assert "post 3 about" not in body
    assert "post 5 about" not in body


async def test_get_posts_filter_by_date_to(app_client, sample_posts):
    """RF-4 acceptance: GET ``/posts?date_to=YYYY-MM-DD`` filters to posts
    on or before the given date (end-of-day inclusive, per the DB layer's
    ``T23:59:59Z`` suffix).
    """
    response = await app_client.get(
        "/posts", params={"date_to": "2024-12-31"}
    )
    assert response.status_code == 200
    body = response.text.lower()
    # post_014 (2024-11-03) must be present.
    assert "post 14 about" in body
    # post_000 (2025-06-01) must NOT be present.
    assert "post 0 about" not in body


async def test_get_posts_filter_by_date_range(app_client, sample_posts):
    """RF-4 acceptance: GET ``/posts?date_from=...&date_to=...`` applies
    both bounds — only posts in the window are returned.
    """
    response = await app_client.get(
        "/posts",
        params={"date_from": "2025-03-01", "date_to": "2025-04-30"},
    )
    assert response.status_code == 200
    body = response.text.lower()
    # post_006 (2025-03-03) is in the window — must be present.
    assert "post 6 about" in body
    # Out-of-window posts must be excluded.
    assert "post 0 about" not in body  # 2025-06-01 (after)
    assert "post 14 about" not in body  # 2024-11-03 (before)


# ── RF-5: responsive media grid end-to-end ────────────────────────────────


async def test_get_posts_post_card_with_media_uses_responsive_grid(
    app_client, sample_posts
):
    """RF-5 acceptance: a post card with media uses the responsive
    ``media-grid`` class — NOT the old fixed ``w-24 h-24`` (96x96px)
    thumbnails. The spec explicitly forbids the fixed 96x96 size.
    """
    response = await app_client.get("/posts")
    assert response.status_code == 200
    body = response.text
    assert "media-grid" in body
    assert "media-grid-item" in body
    # The fixed 96x96 class must be gone.
    assert "w-24 h-24" not in body


async def test_get_posts_post_card_limits_to_four_images(app_client, test_db):
    """RF-5 acceptance: a post with 6+ media URLs renders only 4 images
    (the spec's max-4 limit) through the real HTTP path.
    """
    await _insert_post(
        "many_media",
        "Post with many images",
        "2025-06-01T00:00:00Z",
        [f"https://x.com/m{i}.jpg" for i in range(6)],
    )

    response = await app_client.get("/posts")
    assert response.status_code == 200
    body = response.text
    # Exactly 4 media-grid-item images must be rendered.
    assert body.count("media-grid-item") == 4


async def test_get_posts_post_card_without_media_omits_grid(
    app_client, test_db
):
    """Spec edge case: a post with no media must NOT render an empty
    media-grid (no residual whitespace in the card).
    """
    await _insert_post(
        "no_media_post",
        "Post without images",
        "2025-06-01T00:00:00Z",
        [],
    )

    response = await app_client.get("/posts")
    assert response.status_code == 200
    body = response.text
    assert "media-grid" not in body
    assert "media-grid-item" not in body


# ── RF-6: responsive text in post cards ───────────────────────────────────


async def test_get_posts_post_card_text_uses_break_words(
    app_client, sample_posts
):
    """RF-6 acceptance: post text uses ``break-words`` so long URLs and
    unbroken words do not overflow the card horizontally.
    """
    response = await app_client.get("/posts")
    assert response.status_code == 200
    body = response.text
    assert "break-words" in body


async def test_get_posts_post_card_text_uses_themed_color(
    app_client, sample_posts
):
    """RF-6 acceptance: post text uses ``text-primary``, which maps to the
    active theme variable (``#e7e9ea`` in dark mode, ``#111827`` in light
    mode). This is what gives the text its themed color in both themes.
    """
    response = await app_client.get("/posts")
    body = response.text
    assert "text-primary" in body

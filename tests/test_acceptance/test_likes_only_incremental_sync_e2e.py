"""End-to-end acceptance tests for the likes-only-incremental-sync feature.

These tests verify the acceptance criteria from issues #30-#35 at the
HTTP/route -> DB -> template boundary. They complement (do not duplicate)
the existing tests:

- Unit tests in ``test_frontend/`` render individual templates in isolation
  and assert specific markup pieces.
- Unit tests in ``test_routes/`` exercise the routes with the DB (mostly
  happy-path and per-issue coverage).
- Unit tests in ``tests/js/test_ui_logic.mjs`` exercise the inline JS in a
  Node ``vm`` sandbox.

This file is the acceptance layer: it ties DB state and HTTP rendering
together and asserts the criteria that the spec/promises make about the
end-user experience.

Every test below is mapped to a specific acceptance criterion in issues
#30-#35. Tests that fail are findings (spec violations), not test bugs to
paper over.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

import app.db as db_module
from app.models import XurlPostInput


# ── Helpers ───────────────────────────────────────────────────────────────


def _post_input(post_id: str, **overrides) -> XurlPostInput:
    """Build a XurlPostInput with sensible defaults for a 2026 like."""
    defaults = {
        "id": post_id,
        "text": f"Sample post {post_id}",
        "author_id": f"user_{post_id}",
        "author_username": f"user_{post_id}",
        "author_name": f"User {post_id}",
        "author_avatar": "https://example.com/avatar.jpg",
        "created_at": "2026-01-15T10:00:00Z",
        "media_urls": [],
        "url": f"https://x.com/user_{post_id}/status/{post_id}",
    }
    defaults.update(overrides)
    return XurlPostInput(**defaults)


async def _seed_n_posts(n: int, base_id: str = "post") -> list[str]:
    """Insert n posts with distinct ids; returns the list of ids inserted."""
    now = datetime.now(timezone.utc).isoformat()
    ids: list[str] = []
    base_dt = datetime(2026, 1, 1, tzinfo=timezone.utc)
    for i in range(n):
        post_id = f"{base_id}_{i:04d}"
        created_at = (base_dt + timedelta(hours=i)).strftime("%Y-%m-%dT%H:%M:%SZ")
        await db_module.upsert_post(
            _post_input(post_id, text=f"Post {i}", created_at=created_at),
            "like",
            now,
        )
        ids.append(post_id)
    return ids


# ── Issue #34 acceptance: load-more has no duplicate, counter OOB ────────


async def test_get_posts_load_more_does_not_duplicate_posts(
    app_client, test_db
):
    """Issue #34 acceptance: paginating with 'Load more' does NOT show any
    post twice. The fix was to auto-remove the button after the request
    finishes (otherwise the old button would remain and a second click would
    re-fetch the same page).

    With 50 posts and PAGE_SIZE=20: page 1 has 20, page 2 has 20, page 3
    has 10. We render page 1, then load page 2 (which itself still has a
    load-more button — the fix must also live in the load-more fragment).
    The union of visible posts must be 40 distinct ids (no overlap).
    """
    await _seed_n_posts(50)

    page1 = await app_client.get("/posts")
    assert page1.status_code == 200
    body1 = page1.text
    # The first page must include the load-more button (still more posts).
    assert "Load more" in body1
    assert "load-more-wrap" in body1

    page2 = await app_client.get("/posts/load-more", params={"page": 2})
    assert page2.status_code == 200
    body2 = page2.text

    # Page 2 fragment must ALSO have a load-more button (more posts remain)
    # AND it must be self-removing — the bug is fixed in BOTH the page-1
    # template and the load-more fragment.
    assert "load-more-wrap" in body2
    assert "hx-on::after-request" in body2

    # Count distinct post-card ids in the union of both pages. Posts are
    # identified by their ``/status/<id>`` URL — every card has an "Open
    # original" link to /status/<id>.
    import re

    ids_p1 = set(re.findall(r"/status/(post_\d{4})", body1))
    ids_p2 = set(re.findall(r"/status/(post_\d{4})", body2))
    # Each page renders 20 distinct post ids.
    assert len(ids_p1) == 20
    assert len(ids_p2) == 20
    # And the two pages are disjoint (no duplicates across pages).
    assert ids_p1.isdisjoint(ids_p2), (
        f"load-more returned posts already on page 1: {ids_p1 & ids_p2}"
    )
    assert len(ids_p1 | ids_p2) == 40


async def test_get_posts_load_more_updates_counter_oob(
    app_client, test_db
):
    """Issue #34 acceptance: the load-more fragment updates the post count
    via an out-of-band swap. The counter shows the cumulative count after
    the page boundary (e.g. 'Showing 20 of 50 posts' before the request,
    'Showing 40 of 50 posts' after the load-more appends page 2).
    """
    await _seed_n_posts(50)

    # Page 1 — counter is "Showing 20 of 50 posts".
    page1 = await app_client.get("/posts")
    body1 = page1.text
    assert "Showing 20 of 50" in body1
    # The counter has id="post-count" so HTMX can swap it.
    assert 'id="post-count"' in body1

    # The load-more fragment must contain an OOB swap of the counter.
    fragment = await app_client.get("/posts/load-more", params={"page": 2})
    body2 = fragment.text
    assert 'hx-swap-oob="true"' in body2
    assert 'id="post-count"' in body2
    # The OOB counter reflects the new total (40 of 50).
    assert "Showing 40 of 50" in body2


async def test_get_posts_load_more_button_has_auto_remove_handler(
    app_client, test_db
):
    """Issue #34 acceptance: the load-more button in BOTH the full page
    AND the load-more fragment carries the ``hx-on::after-request`` handler
    that removes the button wrapper after a successful load.

    Needs 50 posts so that page 2 still has remaining posts and therefore
    still renders the load-more button (with the auto-remove handler).
    """
    await _seed_n_posts(50)

    page1 = await app_client.get("/posts")
    assert 'hx-on::after-request="this.closest(\'.load-more-wrap\').remove()"' in page1.text

    fragment = await app_client.get("/posts/load-more", params={"page": 2})
    assert 'hx-on::after-request="this.closest(\'.load-more-wrap\').remove()"' in fragment.text


# ── Issue #34 acceptance: URLs in tweet text are clickable end-to-end ─────


async def test_get_posts_renders_urls_as_clickable_links(
    app_client, test_db
):
    """Issue #34 acceptance: a URL that appears in the tweet text is
    rendered as a clickable ``<a target="_blank" rel="noopener
    noreferrer">`` link in the HTML returned by ``GET /posts`` (not just
    at the model level).
    """
    now = datetime.now(timezone.utc).isoformat()
    await db_module.upsert_post(
        _post_input(
            "with_url_001",
            text="Check https://example.com/foo?a=1&b=2 for more",
        ),
        "like",
        now,
    )

    response = await app_client.get("/posts")
    assert response.status_code == 200
    body = response.text

    # The URL appears as an href, target=_blank, rel=noopener noreferrer.
    assert 'href="https://example.com/foo?a=1&amp;b=2"' in body
    assert 'target="_blank"' in body
    assert 'rel="noopener noreferrer"' in body
    # And the visible text of the link is the URL itself.
    assert ">https://example.com/foo?a=1&amp;b=2</a>" in body


async def test_get_posts_escapes_html_in_tweet_text(app_client, test_db):
    """Issue #34 acceptance: HTML in the tweet text is escaped (so a tweet
    containing ``<script>`` does not inject script tags into the page).
    """
    now = datetime.now(timezone.utc).isoformat()
    await db_module.upsert_post(
        _post_input(
            "xss_001",
            text='hello <script>alert("xss")</script> world',
        ),
        "like",
        now,
    )

    response = await app_client.get("/posts")
    body = response.text
    # The raw <script> tag MUST NOT be in the rendered HTML.
    assert "<script>alert" not in body
    # It is escaped to the entity form.
    assert "&lt;script&gt;alert" in body


# ── Issue #30 acceptance: no 'bookmark' / 'bookmarks' residue in the UI ──


async def test_get_index_no_bookmark_references_in_html(app_client):
    """Issue #30 acceptance: the rendered page does not contain any visible
    bookmark-related text. The sync button is a likes-only button; no
    dropdown, badge, or label mentions 'bookmark' / 'bookmarks'.

    The search bar's source dropdown (which offered 'All / Likes /
    Bookmarks') was removed, and the bookmark badge on post cards was
    removed.
    """
    response = await app_client.get("/")
    body = response.text.lower()
    # No "bookmark" or "bookmarks" in visible UI text.
    assert "bookmark" not in body
    # The source filter was a ``<select name="source">`` combobox; it must
    # not exist in the rendered page.
    assert "name=\"source\"" not in body
    # And the All / Likes / Bookmarks option set must be gone.
    assert "all sources" not in body
    assert "bookmarks</option" not in body


async def test_get_posts_no_bookmark_references_in_html(app_client, test_db):
    """Issue #30 acceptance: the post list fragment also has no bookmark
    references (the badge on each card was removed).
    """
    await db_module.upsert_post(
        _post_input("only_like_001"),
        "like",
        datetime.now(timezone.utc).isoformat(),
    )
    response = await app_client.get("/posts")
    body = response.text.lower()
    assert "bookmark" not in body

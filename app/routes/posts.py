"""Post listing, search, and pagination routes."""

from __future__ import annotations

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse, HTMLResponse

from app.config import PAGE_SIZE
from app.db import get_db, get_posts, search_posts
from app.models import Post

router = APIRouter(prefix="")


@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Main page. Returns the HTML shell (placeholder until templates exist)."""
    html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>xarchive</title>
    <script src="https://unpkg.com/htmx.org@2.0.4"></script>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gray-50 min-h-screen">
    <div id="app" class="max-w-2xl mx-auto p-4">
        <h1 class="text-2xl font-bold mb-4">xarchive</h1>
        <p class="text-gray-600">Your local X.com likes &amp; bookmarks archive.</p>
        <p class="text-sm text-gray-400 mt-2">Backend is running. Templates will be added in the frontend phase.</p>
    </div>
</body>
</html>"""
    return HTMLResponse(content=html)


@router.get("/posts", response_class=HTMLResponse)
async def list_posts(
    request: Request,
    q: str = Query(default="", description="Text search query"),
    username: str = Query(default="", description="Filter by author username"),
    date_from: str = Query(default="", description="Start date (YYYY-MM-DD)"),
    date_to: str = Query(default="", description="End date (YYYY-MM-DD)"),
    source: str = Query(default="all", description="Source filter: like, bookmark, all"),
    page: int = Query(default=1, ge=1, description="Page number"),
):
    """Return paginated, searchable post list.

    Returns HTML fragment when templates exist; JSON placeholder for now.
    Will be switched to Jinja2 template rendering in the frontend phase.
    """
    per_page = PAGE_SIZE
    posts_data, total = await search_posts(
        q=q, username=username, date_from=date_from, date_to=date_to,
        source=source, page=page, per_page=per_page,
    )

    posts = [Post.from_db_row(p) for p in posts_data]

    # Build a simple HTML fragment for the post list
    has_filters = bool(q or username or date_from or date_to or source != "all")

    result_html = _render_post_list_fragment(
        posts=posts,
        total=total,
        page=page,
        per_page=per_page,
        has_filters=has_filters,
        q=q,
        username=username,
        date_from=date_from,
        date_to=date_to,
        source=source,
    )

    return HTMLResponse(content=result_html)


@router.get("/posts/load-more", response_class=HTMLResponse)
async def load_more(
    request: Request,
    q: str = Query(default=""),
    username: str = Query(default=""),
    date_from: str = Query(default=""),
    date_to: str = Query(default=""),
    source: str = Query(default="all"),
    page: int = Query(default=1, ge=1),
):
    """Return next page of post cards as HTML fragment for HTMX append."""
    per_page = PAGE_SIZE
    posts_data, total = await search_posts(
        q=q, username=username, date_from=date_from, date_to=date_to,
        source=source, page=page, per_page=per_page,
    )

    posts = [Post.from_db_row(p) for p in posts_data]

    html = _render_post_cards(posts)

    # Add load-more button if there are more pages
    if page * per_page < total:
        next_page = page + 1
        load_more_url = (
            f"/posts/load-more?page={next_page}"
            f"&q={q}&username={username}&date_from={date_from}"
            f"&date_to={date_to}&source={source}"
        )
        html += (
            f'<div id="load-more-container" class="text-center mt-4">'
            f'<button hx-get="{load_more_url}" hx-swap="outerHTML" '
            f'class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700">'
            f"Load more</button></div>"
        )

    return HTMLResponse(content=html)


@router.get("/api/posts")
async def api_list_posts(
    q: str = Query(default=""),
    username: str = Query(default=""),
    date_from: str = Query(default=""),
    date_to: str = Query(default=""),
    source: str = Query(default="all"),
    page: int = Query(default=1, ge=1),
):
    """JSON API returning posts with pagination info."""
    per_page = PAGE_SIZE
    posts_data, total = await search_posts(
        q=q, username=username, date_from=date_from, date_to=date_to,
        source=source, page=page, per_page=per_page,
    )

    posts = [Post.from_db_row(p).model_dump() for p in posts_data]

    return JSONResponse(
        content={
            "posts": posts,
            "total": total,
            "page": page,
            "per_page": per_page,
        }
    )


# ── Inline HTML render helpers (placeholder until Jinja2 templates exist) ──


def _render_post_cards(posts: list[Post]) -> str:
    """Render a list of post cards as inline HTML."""
    if not posts:
        return '<p class="text-gray-500 text-center py-8">No posts found.</p>'

    cards = ""
    for post in posts:
        source_badge = ""
        if post.is_like:
            source_badge += (
                '<span class="text-xs bg-red-100 text-red-700 px-1.5 py-0.5 rounded">'
                '\u2764\ufe0f like</span> '
            )
        if post.is_bookmark:
            source_badge += (
                '<span class="text-xs bg-yellow-100 text-yellow-700 px-1.5 py-0.5 rounded">'
                '\U0001f516 bookmark</span> '
            )

        media_html = ""
        if post.media_urls:
            media_html = '<div class="flex gap-2 mt-2">'
            for url in post.media_urls[:4]:
                media_html += (
                    f'<img src="{_escape_html(url)}" '
                    f'class="w-24 h-24 object-cover rounded-lg border" '
                    f'alt="media" loading="lazy">'
                )
            media_html += "</div>"

        cards += f"""
        <div class="bg-white rounded-xl shadow-sm border border-gray-100 p-4 mb-3">
            <div class="flex items-start gap-3">
                <img src="{_escape_html(post.author_avatar)}"
                     class="w-10 h-10 rounded-full flex-shrink-0"
                     alt="" loading="lazy">
                <div class="flex-1 min-w-0">
                    <div class="flex items-center gap-2 flex-wrap">
                        <span class="font-semibold text-gray-900 truncate">{_escape_html(post.author_name)}</span>
                        <span class="text-sm text-gray-500">@{_escape_html(post.author_username)}</span>
                        <span class="text-sm text-gray-400">\u00b7 {post.created_at_display}</span>
                        {source_badge}
                    </div>
                    <p class="text-gray-800 mt-1 whitespace-pre-wrap break-words">{_escape_html(post.text)}</p>
                    {media_html}
                    <div class="mt-2">
                        <a href="{_escape_html(post.url)}" target="_blank" rel="noopener"
                           class="text-sm text-blue-600 hover:underline">
                            \U0001f517 Open original
                        </a>
                    </div>
                </div>
            </div>
        </div>"""

    return cards


def _render_post_list_fragment(
    posts: list[Post],
    total: int,
    page: int,
    per_page: int,
    has_filters: bool,
    q: str,
    username: str,
    date_from: str,
    date_to: str,
    source: str,
) -> str:
    """Render the full post list fragment with result count and load more."""
    result_msg = (
        f'<p class="text-sm text-gray-500 mb-3">'
        f'Showing {len(posts)} of {total} posts</p>'
    )

    cards_html = _render_post_cards(posts)

    load_more_html = ""
    if page * per_page < total:
        next_page = page + 1
        params = f"page={next_page}&q={q}&username={username}&date_from={date_from}&date_to={date_to}&source={source}"
        load_more_html = (
            f'<div id="load-more-container" class="text-center mt-4">'
            f'<button hx-get="/posts/load-more?{params}" hx-swap="outerHTML" '
            f'class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition">'
            f"Load more</button></div>"
        )

    return (
        f'<div id="post-list" class="mt-4">'
        f"{result_msg}"
        f"{cards_html}"
        f"{load_more_html}"
        f"</div>"
    )


def _escape_html(text: str) -> str:
    """Basic HTML entity escaping."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#x27;")
    )

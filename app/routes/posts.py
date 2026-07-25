"""Post listing, search, and pagination routes."""

from __future__ import annotations

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse

from app.config import PAGE_SIZE
from app.db import get_db, get_posts, search_posts
from app.main import templates
from app.models import Post

router = APIRouter(prefix="")


@router.get("/")
async def index(request: Request):
    """Main page. Renders the full HTML shell via index.html template."""
    return templates.TemplateResponse(request, "index.html")


@router.get("/posts")
async def list_posts(
    request: Request,
    q: str = Query(default="", description="Text search query"),
    username: str = Query(default="", description="Filter by author username"),
    date_from: str = Query(default="", description="Start date (YYYY-MM-DD)"),
    date_to: str = Query(default="", description="End date (YYYY-MM-DD)"),
    source: str = Query(default="all", description="Source filter: like, bookmark, all"),
    page: int = Query(default=1, ge=1, description="Page number"),
):
    """Return paginated, searchable post list as HTML fragment."""
    per_page = PAGE_SIZE
    posts_data, total = await search_posts(
        q=q, username=username, date_from=date_from, date_to=date_to,
        source=source, page=page, per_page=per_page,
    )

    posts = [Post.from_db_row(p) for p in posts_data]
    has_filters = bool(q or username or date_from or date_to or source != "all")

    return templates.TemplateResponse(
        request,
        "partials/post_list.html",
        {
            "posts": posts,
            "total": total,
            "page": page,
            "per_page": per_page,
            "has_filters": has_filters,
            "q": q,
            "username": username,
            "date_from": date_from,
            "date_to": date_to,
            "source": source,
        },
    )


@router.get("/posts/load-more")
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

    return templates.TemplateResponse(
        request,
        "partials/post_cards_only.html",
        {
            "posts": posts,
            "total": total,
            "page": page,
            "per_page": per_page,
            "q": q,
            "username": username,
            "date_from": date_from,
            "date_to": date_to,
            "source": source,
        },
    )


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

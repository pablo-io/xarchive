"""Sync routes: trigger xurl CLI to import likes incrementally."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.config import SYNC_MIN_CREATED_AT, SYNC_TIMEOUT_SECONDS, XURL_COMMAND, XURL_PAGE_SIZE
from app.db import (
    assign_like_orders,
    create_sync_log,
    get_last_sync_log,
    get_max_like_order,
    get_min_like_order,
    get_sync_resume_state,
    save_sync_token,
    update_sync_log,
    upsert_post,
)
from app.models import XurlPostInput
from app.templating import templates

router = APIRouter(prefix="")

# ── Module-level sync state ─────────────────────────────────────────

_sync_lock: asyncio.Lock = asyncio.Lock()
_sync_in_progress: bool = False
_last_sync_result: dict | None = None

# xurl raw request paths
_ME_PATH = "/2/users/me"
_LIKED_TWEETS_PATH = "/2/users/{user_id}/liked_tweets"


class RateLimitedError(RuntimeError):
    """Raised when the X API returns HTTP 429 (rate limit reached)."""


# ── Helpers ──────────────────────────────────────────────────────────


def _render_sync_button(request: Request, state: str, **kwargs):
    """Render the sync button template for a given state."""
    return templates.TemplateResponse(
        request,
        "partials/sync_button.html",
        {"state": state, **kwargs},
    )


def _parse_dt(value: str) -> datetime | None:
    """Parse an ISO-8601 timestamp into an aware datetime, or None."""
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, TypeError, AttributeError):
        return None


def _build_liked_tweets_path(user_id: str, next_token: str | None) -> str:
    """Build the xurl raw path for a page of liked tweets."""
    params = {
        "max_results": XURL_PAGE_SIZE,
        "tweet.fields": "created_at,entities,attachments",
        "expansions": "author_id,attachments.media_keys",
        "user.fields": "username,name,profile_image_url",
        "media.fields": "url,preview_image_url,type",
    }
    if next_token:
        params["pagination_token"] = next_token
    qs = "&".join(f"{k}={v}" for k, v in params.items())
    return f"{_LIKED_TWEETS_PATH.format(user_id=user_id)}?{qs}"


def _adapt_post(raw: dict, users: dict, media: dict) -> XurlPostInput | None:
    """Adapt one raw liked_tweets item into a XurlPostInput.

    The raw item carries only ``author_id``; the author's username/name/avatar
    live in ``includes.users``. Media URLs are resolved from
    ``attachments.media_keys`` via ``includes.media``.
    """
    author = users.get(raw.get("author_id"))
    username = author.get("username", "") if author else ""

    media_urls: list[str] = []
    for key in (raw.get("attachments") or {}).get("media_keys", []):
        m = media.get(key)
        if not m:
            continue
        url = m.get("url") or m.get("preview_image_url")
        if url:
            media_urls.append(url)

    try:
        return XurlPostInput(
            id=raw["id"],
            text=raw.get("text", ""),
            author_id=raw.get("author_id", ""),
            author_username=username,
            author_name=author.get("name", "") if author else "",
            author_avatar=author.get("profile_image_url", "") if author else "",
            created_at=raw.get("created_at", ""),
            media_urls=media_urls,
            url=f"https://x.com/{username}/status/{raw['id']}",
        )
    except (ValueError, TypeError, KeyError):
        return None


# ── Routes ──────────────────────────────────────────────────────────


@router.post("/sync")
async def trigger_sync(request: Request):
    """Trigger a manual sync of likes via the xurl CLI.

    Incremental: likes are paged from the newest like; import stops at the
    first post already in the database (or at the 2026 cutoff). If the X API
    rate limit is hit, the pagination token is persisted so the next sync
    resumes where it left off.

    Returns an HTML fragment with the sync button result state.
    """
    global _sync_in_progress, _last_sync_result

    async with _sync_lock:
        if _sync_in_progress:
            return _render_sync_button(request, "error", error_message="A sync is already in progress.")

        _sync_in_progress = True
        log_id = await create_sync_log("likes")
        try:
            new_count, updated_count = await _run_xurl_sync(log_id)
            await update_sync_log(log_id, "success", posts_new=new_count, posts_updated=updated_count)
        except RateLimitedError as e:
            await update_sync_log(log_id, "error", error_message=str(e))
            _last_sync_result = {
                "status": "rate_limited",
                "new": 0,
                "updated": 0,
                "error": str(e),
            }
            return _render_sync_button(
                request, "error",
                new_count=0, updated_count=0,
                error_message=str(e),
            )
        except Exception as e:
            error_msg = str(e)
            await update_sync_log(log_id, "error", error_message=error_msg)
            _last_sync_result = {
                "status": "error",
                "new": 0,
                "updated": 0,
                "error": error_msg,
            }
            return _render_sync_button(request, "error", new_count=0, updated_count=0, error_message=error_msg)
        finally:
            _sync_in_progress = False

        _last_sync_result = {
            "status": "success",
            "new": new_count,
            "updated": updated_count,
        }
        response = _render_sync_button(request, "success", new_count=new_count, updated_count=updated_count)
        response.headers["HX-Trigger"] = "postsChanged"
        return response


@router.get("/sync/status")
async def sync_status(request: Request):
    """Return current sync status as HTML fragment (used for polling)."""
    global _sync_in_progress, _last_sync_result

    if _sync_in_progress:
        return _render_sync_button(request, "running")
    elif _last_sync_result:
        r = _last_sync_result
        return _render_sync_button(
            request,
            r["status"],
            new_count=r.get("new", 0),
            updated_count=r.get("updated", 0),
            error_message=r.get("error"),
        )
    else:
        return _render_sync_button(request, "idle")


@router.get("/api/sync/status")
async def api_sync_status():
    """JSON endpoint returning the last sync log info."""
    last = await get_last_sync_log()
    if last is None:
        return JSONResponse(content={"status": "never", "message": "No sync has been performed yet."})

    return JSONResponse(
        content={
            "id": last.get("id"),
            "status": last.get("status"),
            "source_type": last.get("source_type"),
            "started_at": last.get("started_at"),
            "finished_at": last.get("finished_at"),
            "posts_new": last.get("posts_new"),
            "posts_updated": last.get("posts_updated"),
            "error_message": last.get("error_message"),
        }
    )


# ── Sync implementation ─────────────────────────────────────────────


async def _run_xurl_json(path: str) -> dict:
    """Execute ``xurl <path>`` and return the parsed JSON object.

    Raises:
        FileNotFoundError: xurl CLI is not installed.
        asyncio.TimeoutError: xurl took too long.
        RateLimitedError: the X API returned HTTP 429.
        RuntimeError: xurl exited with another non-zero code.
        json.JSONDecodeError: xurl output was not valid JSON.
    """
    try:
        process = await asyncio.create_subprocess_exec(
            XURL_COMMAND,
            path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                process.communicate(),
                timeout=SYNC_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
            raise asyncio.TimeoutError(
                f"Sync timed out after {SYNC_TIMEOUT_SECONDS}s. Try again."
            )

    except FileNotFoundError:
        raise FileNotFoundError("xurl CLI not found. Install it first.")

    stdout_text = stdout_bytes.decode("utf-8", errors="replace").strip()
    stderr_text = stderr_bytes.decode("utf-8", errors="replace").strip()

    if process.returncode != 0:
        if "Too Many Requests" in stdout_text or "request failed" in stderr_text:
            raise RateLimitedError(
                "Rate limit reached. Progress was saved — press Sync again in ~15 minutes to continue."
            )
        raise RuntimeError(f"Sync failed: {stderr_text}" if stderr_text else f"xurl exited with code {process.returncode}")

    if not stdout_text:
        return {}

    try:
        payload = json.loads(stdout_text)
    except json.JSONDecodeError as e:
        raise json.JSONDecodeError(
            f"Unexpected response from xurl: {e.msg}",
            e.doc,
            e.pos,
        )

    if not isinstance(payload, dict):
        raise RuntimeError(f"Unexpected response from xurl: expected a JSON object, got {type(payload).__name__}")

    return payload


async def _run_xurl_sync(log_id: int) -> tuple[int, int]:
    """Fetch likes via the raw X API, importing only those not yet synced.

    The API orders likes by when the *like* happened (most recent first), not
    by the tweet's ``created_at``. We page through the newest likes and stop
    as soon as we hit a post that is already in the database, or a post whose
    ``created_at`` predates the 2026 cutoff.

    Pagination resumes from a persisted token when the previous sync was cut
    off by the rate limit. Each imported post gets a ``like_order`` so the
    list can be shown newest-like-first.

    Returns:
        (new_count, updated_count) — number of new and updated posts.
    """
    me = await _run_xurl_json(_ME_PATH)
    try:
        user_id = me["data"]["id"]
    except (KeyError, TypeError):
        raise RuntimeError("Unexpected response from xurl: could not find the authenticated user.")

    resume = await get_sync_resume_state()
    next_token = resume["next_token"] if resume else None
    mode = resume["like_order_mode"] if resume else ("backfill" if await get_max_like_order() == 0 else "incremental")

    new_count = 0
    updated_count = 0
    new_post_ids: list[str] = []
    now = datetime.now(timezone.utc).isoformat()
    cutoff = _parse_dt(SYNC_MIN_CREATED_AT)

    try:
        while True:
            path = _build_liked_tweets_path(user_id, next_token)
            payload = await _run_xurl_json(path)

            data = payload.get("data", [])
            if not data:
                break

            includes = payload.get("includes", {})
            users = {u["id"]: u for u in includes.get("users", [])}
            media = {m["media_key"]: m for m in includes.get("media", [])}

            stop = False
            for raw in data:
                created_dt = _parse_dt(raw.get("created_at"))
                if created_dt is not None and cutoff is not None and created_dt < cutoff:
                    stop = True
                    break

                post = _adapt_post(raw, users, media)
                if post is None:
                    continue

                result = await upsert_post(post, "like", now)
                if result == "new":
                    new_count += 1
                    new_post_ids.append(post.id)
                elif result == "updated":
                    # This post was already synced — every remaining like is
                    # older and also already synced, so stop paginating.
                    stop = True
                    break

            next_token = (payload.get("meta") or {}).get("next_token")
            await save_sync_token(log_id, next_token, mode)

            if stop or not next_token:
                break

        await save_sync_token(log_id, None, mode)
    except RateLimitedError:
        # The token from the last successful page is already persisted.
        raise
    finally:
        await _assign_like_orders(mode, new_post_ids)

    return new_count, updated_count


async def _assign_like_orders(mode: str, new_post_ids: list[str]) -> None:
    """Assign like_order to newly imported posts.

    In ``backfill`` mode the posts are older than everything already stored
    (or the table was empty), so they get values below the current minimum.
    In ``incremental`` mode they are newer than everything, so they get values
    above the current maximum. Higher = more recently liked.
    """
    if not new_post_ids:
        return

    if mode == "backfill":
        base = (await get_min_like_order()) - 1
    else:
        base = (await get_max_like_order()) + len(new_post_ids)

    await assign_like_orders(new_post_ids, base)

"""Sync routes: trigger xurl CLI to import likes and bookmarks."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse

from app.config import SYNC_TIMEOUT_SECONDS
from app.db import (
    create_sync_log,
    get_last_sync_log,
    upsert_post,
    update_sync_log,
)
from app.models import XurlPostInput

router = APIRouter(prefix="")

# ── Module-level sync state ─────────────────────────────────────────

_sync_lock: asyncio.Lock = asyncio.Lock()
_sync_in_progress: bool = False
_last_sync_result: dict | None = None

# Source → xurl command mapping
_SOURCE_COMMANDS: dict[str, str] = {
    "likes": "likes",
    "bookmarks": "bookmarks",
}


# ── Routes ──────────────────────────────────────────────────────────


@router.post("/sync")
async def trigger_sync(
    request: Request,
    source_type: str = Form(default="both"),
):
    """Trigger a manual sync of likes and/or bookmarks via the xurl CLI.

    Form parameter: source_type = "likes" | "bookmarks" | "both"
    Returns: HTML fragment with sync button result state.
    """
    global _sync_in_progress, _last_sync_result

    if _sync_in_progress:
        html = _render_sync_button_fragment("error", error_message="A sync is already in progress.")
        return HTMLResponse(content=html)

    # Determine which sources to sync
    if source_type == "both":
        sources = ["likes", "bookmarks"]
    elif source_type in ("likes", "bookmarks"):
        sources = [source_type]
    else:
        html = _render_sync_button_fragment("error", error_message=f"Invalid source_type: '{source_type}'. Use 'likes', 'bookmarks', or 'both'.")
        return HTMLResponse(content=html)

    async with _sync_lock:
        _sync_in_progress = True
        total_new = 0
        total_updated = 0
        errors: list[str] = []

        for src in sources:
            log_id = await create_sync_log(src)
            try:
                new_count, updated_count = await _run_xurl_sync(src)
                total_new += new_count
                total_updated += updated_count
                await update_sync_log(log_id, "success", posts_new=new_count, posts_updated=updated_count)
            except Exception as e:
                error_msg = str(e)
                errors.append(f"{src}: {error_msg}")
                await update_sync_log(log_id, "error", error_message=error_msg)

        _sync_in_progress = False

        if errors:
            _last_sync_result = {
                "status": "error",
                "new": total_new,
                "updated": total_updated,
                "error": "; ".join(errors),
            }
            html = _render_sync_button_fragment("error", new_count=total_new, updated_count=total_updated, error_message="; ".join(errors))
        else:
            _last_sync_result = {
                "status": "success",
                "new": total_new,
                "updated": total_updated,
            }
            html = _render_sync_button_fragment("success", new_count=total_new, updated_count=total_updated)

        # Return with HX-Trigger header to refresh the post list
        return HTMLResponse(
            content=html,
            headers={"HX-Trigger": "postsChanged"},
        )


@router.get("/sync/status")
async def sync_status(request: Request):
    """Return current sync status as HTML fragment (used for polling)."""
    global _sync_in_progress, _last_sync_result

    if _sync_in_progress:
        html = _render_sync_button_fragment("running")
    elif _last_sync_result:
        r = _last_sync_result
        html = _render_sync_button_fragment(
            r["status"],
            new_count=r.get("new", 0),
            updated_count=r.get("updated", 0),
            error_message=r.get("error"),
        )
    else:
        html = _render_sync_button_fragment("idle")

    return HTMLResponse(content=html)


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


async def _run_xurl_sync(source: str) -> tuple[int, int]:
    """Execute `xurl <source>` (e.g., `xurl likes`), parse JSON output,
    and upsert each post into the database.

    Args:
        source: Either "likes" or "bookmarks".

    Returns:
        (new_count, updated_count) — number of new and updated posts.

    Raises:
        FileNotFoundError: xurl CLI is not installed.
        asyncio.TimeoutError: xurl took too long.
        RuntimeError: xurl exited with non-zero code.
        json.JSONDecodeError: xurl output was not valid JSON.
    """
    from app.config import XURL_COMMAND

    cmd = _SOURCE_COMMANDS.get(source, source)

    try:
        process = await asyncio.create_subprocess_exec(
            XURL_COMMAND,
            cmd,
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

    if process.returncode != 0:
        stderr_text = stderr_bytes.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"Sync failed: {stderr_text}" if stderr_text else f"xurl exited with code {process.returncode}")

    # Parse JSON output
    stdout_text = stdout_bytes.decode("utf-8", errors="replace").strip()

    if not stdout_text:
        # No output — no posts
        return 0, 0

    try:
        raw_posts: list[dict] = json.loads(stdout_text)
    except json.JSONDecodeError as e:
        raise json.JSONDecodeError(
            f"Unexpected response from xurl: {e.msg}",
            e.doc,
            e.pos,
        )

    if not isinstance(raw_posts, list):
        raise RuntimeError(f"Unexpected response from xurl: expected a JSON array, got {type(raw_posts).__name__}")

    # Upsert each post
    now = datetime.now(timezone.utc).isoformat()
    new_count = 0
    updated_count = 0

    for raw in raw_posts:
        try:
            post_input = XurlPostInput.model_validate(raw)
        except Exception:
            # Skip individual items that don't match the expected schema
            continue

        result = await upsert_post(post_input, source, now)
        if result == "new":
            new_count += 1
        else:
            updated_count += 1

    return new_count, updated_count


# ── Inline HTML render helpers ──────────────────────────────────────


def _render_sync_button_fragment(
    state: str,
    new_count: int = 0,
    updated_count: int = 0,
    error_message: str | None = None,
) -> str:
    """Render the sync button HTML fragment for different states.

    States: idle, running, success, error
    """
    if state == "running":
        return (
            '<div id="sync-button" class="inline-flex items-center gap-2">'
            '<span class="animate-spin text-lg">\u27f3</span>'
            '<span class="text-blue-600 font-medium">Syncing...</span>'
            "</div>"
        )

    if state == "success":
        msg = f"\u2713 Synced {new_count} new, {updated_count} updated"
        return (
            f'<div id="sync-button" class="inline-flex items-center gap-2">'
            f'<span class="text-green-600 font-medium">{msg}</span>'
            f'<button hx-post="/sync" hx-target="#sync-button" hx-swap="outerHTML" '
            f'class="text-sm text-blue-600 hover:underline ml-2" name="source_type" value="both">'
            f"Sync again</button>"
            f"</div>"
        )

    if state == "error":
        msg = f"\u2717 {error_message}" if error_message else "\u2717 Sync failed"
        return (
            f'<div id="sync-button" class="inline-flex items-center gap-2">'
            f'<span class="text-red-600 font-medium">{msg}</span>'
            f'<button hx-post="/sync" hx-target="#sync-button" hx-swap="outerHTML" '
            f'class="text-sm text-blue-600 hover:underline ml-2" name="source_type" value="both">'
            f"Retry</button>"
            f"</div>"
        )

    # idle
    # Source: https://htmx.org/attributes/hx-post/
    return (
        '<div id="sync-button" class="inline-flex items-center gap-2">'
        '<button hx-post="/sync" hx-target="#sync-button" hx-swap="outerHTML" '
        'class="px-3 py-1.5 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition text-sm font-medium" '
        'name="source_type" value="both">'
        '\u27f3 Sync all</button>'
        '<button hx-post="/sync" hx-target="#sync-button" hx-swap="outerHTML" '
        'class="px-3 py-1.5 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition text-sm font-medium" '
        'name="source_type" value="likes">'
        'Sync likes</button>'
        '<button hx-post="/sync" hx-target="#sync-button" hx-swap="outerHTML" '
        'class="px-3 py-1.5 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition text-sm font-medium" '
        'name="source_type" value="bookmarks">'
        'Sync bookmarks</button>'
        "</div>"
    )

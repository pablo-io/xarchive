"""FastAPI application factory for xarchive.

Wires together lifespan, static files, template engine, and routers.
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.config import HOST, PORT
from app.db import close_db, init_db
from app.routes import posts, sync

# Jinja2 templates — importable by route handlers via `from app.main import templates`
templates = Jinja2Templates(directory="app/templates")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: initialize DB on startup, close on shutdown."""
    await init_db()
    try:
        yield
    finally:
        await close_db()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="xarchive",
        description="Local X.com (Twitter) likes and bookmarks archive with search",
        version="0.1.0",
        lifespan=lifespan,
    )

    # Static files mount
    static_dir = "app/static"
    if not os.path.isdir(static_dir):
        os.makedirs(static_dir, exist_ok=True)
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    # Include routers
    app.include_router(posts.router)
    app.include_router(sync.router)

    return app


app: FastAPI = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host=HOST, port=PORT, reload=True)

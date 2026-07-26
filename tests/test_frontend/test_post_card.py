"""Unit tests for responsive post-card media grid (Tarea 6).

Renders ``partials/post_card.html`` and asserts the media grid markup, the
image count limit, themed classes, and the corresponding CSS rules.
"""

from __future__ import annotations

from pathlib import Path

CSS_PATH = Path(__file__).resolve().parents[2] / "app" / "static" / "css" / "custom.css"

from app.templating import templates


def make_post(media_count: int = 0) -> dict:
    return {
        "author_avatar": "https://example.com/a.jpg",
        "author_name": "Alice",
        "author_username": "alice",
        "created_at_display": "2025-01-01",
        "is_like": False,
        "is_bookmark": False,
        "text": "hello world",
        "media_urls": [f"https://example.com/m{i}.jpg" for i in range(media_count)],
        "url": "https://x.com/alice/status/1",
    }


def render(post: dict) -> str:
    return templates.get_template("partials/post_card.html").render(post=post)


def test_media_grid_present_with_images():
    html = render(make_post(2))
    assert "media-grid" in html
    assert "media-grid-item" in html
    assert "object-cover" in html


def test_media_grid_limits_to_four_images():
    html = render(make_post(6))
    assert html.count("media-grid-item") == 4


def test_no_media_renders_no_grid():
    html = render(make_post(0))
    assert "media-grid" not in html
    assert "media-grid-item" not in html


def test_images_use_themed_border():
    html = render(make_post(1))
    assert "border-themed" in html


def test_post_text_uses_text_primary():
    html = render(make_post(0))
    assert "text-primary" in html
    assert "break-words" in html


def test_card_uses_themed_background_and_border():
    html = render(make_post(0))
    assert "card-bg" in html
    assert "border-themed" in html


def test_css_defines_media_grid_rules():
    css = CSS_PATH.read_text(encoding="utf-8")
    assert ".media-grid {" in css
    assert ".media-grid-item" in css
    assert "width: 100%" in css
    assert "height: auto" in css

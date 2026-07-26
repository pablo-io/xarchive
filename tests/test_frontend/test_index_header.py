"""Unit tests for the redesigned header (Tarea 3).

Renders the full ``index.html`` and asserts the header exposes the four
expected controls (title, sync, search toggle, theme toggle) with the correct
aria-labels, onclick handlers, themed classes, and the toggleSearchBar helper.
"""

from __future__ import annotations

import html as _html

from app.templating import templates


def render_index() -> str:
    return _html.unescape(templates.get_template("index.html").render())


def test_header_contains_title():
    html = render_index()
    assert "xarchive" in html
    assert "📦" in html


def test_header_has_four_controls():
    html = render_index()
    assert 'id="sync-button"' in html
    assert 'id="search-toggle"' in html
    assert 'id="theme-toggle"' in html


def test_search_toggle_has_aria_and_handler():
    html = render_index()
    btn = html[html.index('id="search-toggle"') : html.index(">", html.index('id="search-toggle"'))]
    assert 'aria-label="Toggle search bar"' in html
    assert 'onclick="toggleSearchBar()"' in html


def test_theme_toggle_has_aria_and_handler():
    html = render_index()
    assert 'aria-label="Toggle dark theme"' in html
    assert 'onclick="toggleTheme()"' in html


def test_header_uses_themed_classes():
    html = render_index()
    assert "card-bg" in html
    assert "border-themed" in html
    assert "bg-hover" in html


def test_toggle_search_bar_function_defined():
    html = render_index()
    assert "function toggleSearchBar" in html

"""Unit tests for the search-bar visibility toggle (Tarea 4).

Renders ``index.html`` and asserts the ``#search-bar-wrapper`` exists (hidden by
default, wrapping the search form) and that the ``hasSearchParams`` helper and
auto-show logic are present. Also checks the CSS transition rules.
"""

from __future__ import annotations

from pathlib import Path

CSS_PATH = Path(__file__).resolve().parents[2] / "app" / "static" / "css" / "custom.css"

from app.templating import templates


def render_index() -> str:
    return templates.get_template("index.html").render()


def test_search_bar_wrapper_present_and_hidden():
    html = render_index()
    assert 'id="search-bar-wrapper"' in html
    assert "search-bar-wrapper hidden" in html


def test_search_bar_form_is_inside_wrapper():
    html = render_index()
    assert 'hx-get="/posts"' in html  # search_bar form target
    assert html.index('id="search-bar-wrapper"') < html.index('hx-get="/posts"')


def test_has_search_params_function_defined():
    html = render_index()
    assert "function hasSearchParams" in html


def test_auto_show_on_load_present():
    html = render_index()
    assert "hasSearchParams()" in html


def test_css_defines_search_bar_wrapper_rules():
    css = CSS_PATH.read_text(encoding="utf-8")
    assert ".search-bar-wrapper {" in css
    assert ".search-bar-wrapper.hidden" in css
    assert ".search-bar-wrapper:not(.hidden)" in css
    assert "max-height: 0" in css
    assert "max-height: 500px" in css
    assert "transition: max-height 300ms" in css

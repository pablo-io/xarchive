"""Unit tests for compact date fields in the search bar (Tarea 5).

Renders ``partials/search_bar.html`` and asserts the compact date labels, the
hidden-but-functional date inputs, the ``updateDateLabel`` helper, and the
corresponding CSS rules. The search form is also themed so it is not a white
box in dark mode.
"""

from __future__ import annotations

from pathlib import Path

CSS_PATH = Path(__file__).resolve().parents[2] / "app" / "static" / "css" / "custom.css"

from app.templating import templates


def render_search(date_from: str = "", date_to: str = "") -> str:
    return templates.get_template("partials/search_bar.html").render(
        q="", username="", date_from=date_from, date_to=date_to, source="all"
    )


def test_compact_date_labels_present():
    html = render_search()
    assert 'id="label-date-from"' in html
    assert 'id="label-date-to"' in html
    assert "date-compact-btn" in html
    assert html.count("date-compact-btn") == 2


def test_date_inputs_hidden_but_functional():
    html = render_search()
    assert 'type="date"' in html
    assert 'name="date_from"' in html
    assert 'name="date_to"' in html
    assert "opacity-0" in html
    assert "cursor-pointer" in html


def test_date_labels_call_updateDateLabel():
    html = render_search()
    assert "onchange=\"updateDateLabel('date-from', this.value)\"" in html
    assert "onchange=\"updateDateLabel('date-to', this.value)\"" in html


def test_date_label_shows_value_when_present():
    html = render_search(date_from="2025-01-15", date_to="")
    from_label = html[html.index('id="label-date-from"') : html.index('id="label-date-to"')]
    assert "📅 2025-01-15" in from_label
    assert "Inicio" not in from_label
    to_label = html[html.index('id="label-date-to"') : html.index("</form>")]
    assert "Fin" in to_label


def test_date_labels_show_default_text_when_empty():
    html = render_search()
    assert "Inicio" in html
    assert "Fin" in html


def test_update_date_label_function_defined():
    html = render_search()
    assert "function updateDateLabel" in html


def test_search_form_is_themed():
    html = render_search()
    assert "card-bg" in html
    assert "border-themed" in html


def test_css_defines_date_compact_rules():
    css = CSS_PATH.read_text(encoding="utf-8")
    assert ".date-compact-btn {" in css
    assert ".date-compact-text" in css
    assert ".date-compact-btn:hover" in css

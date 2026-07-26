"""Unit tests for the simplified Sync button (Tarea 1).

These tests render the ``partials/sync_button.html`` template directly and
assert the structure required by the design contract: in the idle state there
must be NO <select> combobox and the submit button must carry
``name="source_type" value="both"``.
"""

from __future__ import annotations

from app.templating import templates


def render_sync(state: str) -> str:
    return templates.get_template("partials/sync_button.html").render(state=state)


def test_idle_has_no_select_combobox():
    html = render_sync("idle")
    assert "<select" not in html.lower()


def test_idle_button_carries_source_type_both():
    html = render_sync("idle")
    assert 'name="source_type"' in html
    assert 'value="both"' in html


def test_idle_form_posts_to_sync_with_htmx():
    html = render_sync("idle")
    assert 'hx-post="/sync"' in html
    assert 'hx-target="#sync-button"' in html
    assert 'hx-swap="outerHTML"' in html


def test_idle_submit_button_has_aria_label():
    html = render_sync("idle")
    assert 'type="submit"' in html
    assert "🔄" in html or "&#10227;" in html


def test_other_states_render_without_error():
    for state in ("running", "success", "error"):
        html = render_sync(state)
        assert isinstance(html, str)
        # These states never introduce a <select> either.
        assert "<select" not in html.lower()

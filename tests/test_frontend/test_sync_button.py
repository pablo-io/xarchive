"""Unit tests for the simplified Sync button (Tarea 1).

These tests render the ``partials/sync_button.html`` template directly and
assert the structure required by the design contract: in the idle state there
must be NO <select> combobox and the submit button posts directly to ``/sync``
without a ``source_type`` field (only likes are synced now).
"""

from __future__ import annotations

from app.templating import templates


def render_sync(state: str) -> str:
    return templates.get_template("partials/sync_button.html").render(state=state)


def test_idle_has_no_select_combobox():
    html = render_sync("idle")
    assert "<select" not in html.lower()


def test_idle_button_posts_to_sync_without_source_type():
    html = render_sync("idle")
    assert 'hx-post="/sync"' in html
    assert 'name="source_type"' not in html


def test_idle_form_posts_to_sync_with_htmx():
    html = render_sync("idle")
    assert 'hx-post="/sync"' in html
    assert 'hx-target="#sync-button"' in html
    assert 'hx-swap="outerHTML"' in html


def test_idle_submit_button_has_aria_label():
    html = render_sync("idle")
    assert 'type="submit"' in html
    assert "&#128260;" in html  # 🔄 sync icon
    assert 'aria-label="Sync likes"' in html


def test_idle_button_is_icon_only():
    """The idle sync button is an icon with no visible text."""
    html = render_sync("idle")
    assert "Sync" not in html.replace("Sync likes", "").replace("aria-label", "")
    assert "p-2 rounded-lg bg-hover text-primary text-lg" in html


def test_other_states_render_without_error():
    for state in ("running", "success", "error"):
        html = render_sync(state)
        assert isinstance(html, str)
        # These states never introduce a <select> either.
        assert "<select" not in html.lower()

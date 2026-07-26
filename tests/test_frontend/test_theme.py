"""Unit tests for the dark-theme CSS variable system (Tarea 2).

These tests assert that ``app/static/css/custom.css`` defines the light/dark
CSS variables and the custom utility classes that the theme toggle relies on.
"""

from __future__ import annotations

from pathlib import Path

CSS_PATH = Path(__file__).resolve().parents[2] / "app" / "static" / "css" / "custom.css"

LIGHT_VARS = {
    "--bg-page": "#f9fafb",
    "--bg-card": "#ffffff",
    "--text-primary": "#111827",
    "--text-secondary": "#6b7280",
    "--border-color": "#e5e7eb",
    "--accent-color": "#2563eb",
    "--bg-hover": "#f3f4f6",
}

DARK_VARS = {
    "--bg-page": "#000000",
    "--bg-card": "#16181c",
    "--text-primary": "#e7e9ea",
    "--text-secondary": "#71767b",
    "--border-color": "#2f3336",
    "--accent-color": "#1d9bf0",
    "--bg-hover": "#181818",
}

UTILITY_CLASSES = [
    ".card-bg",
    ".text-primary",
    ".text-secondary",
    ".border-themed",
    ".bg-page",
    ".accent",
    ".bg-hover",
]


def _css() -> str:
    return CSS_PATH.read_text(encoding="utf-8")


def test_light_theme_variables_defined():
    css = _css()
    assert ":root" in css
    for name, value in LIGHT_VARS.items():
        assert f"{name}: {value}" in css, f"missing light var {name}: {value}"


def test_dark_theme_variables_defined():
    css = _css()
    assert '[data-theme="dark"]' in css
    for name, value in DARK_VARS.items():
        # Variable may be declared inside the dark block; allow for the
        # declaration anywhere after the dark selector.
        assert f"{name}: {value}" in css, f"missing dark var {name}: {value}"


def test_utility_classes_defined():
    css = _css()
    for cls in UTILITY_CLASSES:
        assert cls in css, f"missing utility class {cls}"


def test_bg_hover_has_hover_state():
    css = _css()
    assert ".bg-hover:hover" in css


def test_variables_map_to_utility_classes():
    css = _css()
    assert "background-color: var(--bg-card)" in css
    assert "color: var(--text-primary)" in css
    assert "color: var(--text-secondary)" in css
    assert "border-color: var(--border-color)" in css
    assert "background-color: var(--bg-page)" in css

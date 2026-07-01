"""Textual terminal UI entry point."""

from textual.app import App


class LaTeXTransTuiApp(App[None]):
    """Minimal Textual application shell for packaging tests."""


def run() -> None:
    """Run the LaTeXTransPlus terminal UI."""
    LaTeXTransTuiApp().run()

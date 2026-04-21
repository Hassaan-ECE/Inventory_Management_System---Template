"""UI-focused helpers for the main inventory window shell."""

from __future__ import annotations

from PySide6.QtGui import QGuiApplication


def apply_initial_window_size(window) -> None:
    """Size the main window to the current display instead of assuming a large monitor."""
    min_width = 960
    min_height = 640
    window.setMinimumSize(min_width, min_height)

    screen = QGuiApplication.primaryScreen()
    if screen is None:
        window.resize(1280, 800)
        return

    available = screen.availableGeometry()
    compact_display = available.width() <= 1920 or available.height() <= 1080

    target_width = 1220 if compact_display else 1360
    target_height = 760 if compact_display else 860

    width = min(target_width, max(min_width, available.width() - 120))
    height = min(target_height, max(min_height, available.height() - 120))
    window.resize(width, height)


__all__ = ["apply_initial_window_size"]

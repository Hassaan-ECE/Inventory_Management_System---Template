"""Shared window title and icon helpers."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QWidget

from Code.utils.runtime_paths import bundle_root, executable_dir

APPLICATION_WINDOW_TITLE = "Inventory Management System"
_ICON_FILENAME = "app_icon.ico"


def build_window_title(section: str = "") -> str:
    """Return a consistent branded title for top-level windows."""
    section = section.strip()
    if not section:
        return APPLICATION_WINDOW_TITLE
    return f"{APPLICATION_WINDOW_TITLE} - {section}"


@lru_cache(maxsize=1)
def resolve_app_icon_path() -> Path | None:
    """Locate the shared application icon in source or packaged layouts."""
    candidates = (
        bundle_root().parent / "shared_core" / "assets" / _ICON_FILENAME,
        bundle_root() / "shared_core" / "assets" / _ICON_FILENAME,
        bundle_root() / "assets" / _ICON_FILENAME,
        executable_dir().parent / "shared_core" / "assets" / _ICON_FILENAME,
        executable_dir() / "shared_core" / "assets" / _ICON_FILENAME,
        executable_dir() / "assets" / _ICON_FILENAME,
    )
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


@lru_cache(maxsize=1)
def app_icon() -> QIcon:
    """Return the branded app icon when available."""
    icon_path = resolve_app_icon_path()
    if icon_path is None:
        return QIcon()
    return QIcon(str(icon_path))


def apply_window_branding(window: QWidget, section: str = "") -> None:
    """Apply the shared title format and icon to a top-level window."""
    window.setWindowTitle(build_window_title(section))
    icon = app_icon()
    if not icon.isNull():
        window.setWindowIcon(icon)

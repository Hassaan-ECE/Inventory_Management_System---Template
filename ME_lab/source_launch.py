"""Source-run helpers for launching the ME app with explicit DB overrides."""

from __future__ import annotations

import os
from pathlib import Path

from app_config import APP_CONFIG


def configure_source_db_path() -> Path | None:
    """Optionally opt source runs into the installed per-user database.

    Source runs now stay on the repo-local database by default. To point
    ``python main.py`` at the installed per-user database for a quick manual
    comparison, set ``ME_LAB_SOURCE_USE_INSTALLED_DB=1`` before launch.
    """
    if _is_compiled_runtime():
        return None

    env_var = APP_CONFIG.db_path_env_var
    configured = os.environ.get(env_var, "").strip()
    if configured:
        return Path(os.path.expandvars(configured)).expanduser()

    if not _source_should_use_installed_db():
        return None

    local_appdata = os.environ.get("LOCALAPPDATA", "").strip()
    if not local_appdata:
        return None

    candidate = Path(local_appdata) / APP_CONFIG.app_dir_name / APP_CONFIG.db_filename
    if not candidate.exists():
        return None

    os.environ[env_var] = str(candidate)
    return candidate


def _source_should_use_installed_db() -> bool:
    """Return whether a source run should borrow the installed local DB."""
    raw = os.environ.get("ME_LAB_SOURCE_USE_INSTALLED_DB", "").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def _is_compiled_runtime() -> bool:
    """Return whether the current process is running from a compiled bundle."""
    try:
        __compiled__  # type: ignore[name-defined]
    except NameError:
        return False
    return True

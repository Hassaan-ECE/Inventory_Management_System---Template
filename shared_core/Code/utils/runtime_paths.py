"""Runtime path helpers for source and compiled builds."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import app_config as app_config_module

from app_config import APP_CONFIG

APP_DIR_NAME = APP_CONFIG.app_dir_name
DB_FILENAME = APP_CONFIG.db_filename
DB_PATH_ENV_VAR = APP_CONFIG.db_path_env_var


def bundle_root() -> Path:
    """Return the active app root directory for the current variant."""
    config_file = getattr(app_config_module, "__file__", "")
    if config_file:
        return Path(config_file).resolve().parent
    return Path(sys.argv[0]).resolve().parent


def executable_dir() -> Path:
    """Return the directory that contains the launched program."""
    try:
        return Path(__compiled__.containing_dir)  # type: ignore[name-defined]
    except NameError:
        return Path(sys.argv[0]).resolve().parent


def bundled_data_dir() -> Path:
    """Return the application-owned Data directory inside the bundle."""
    return bundle_root() / "Data"


def external_data_dir() -> Path:
    """Return the optional Data directory next to the launched program."""
    return executable_dir() / "Data"


def resolve_data_dir() -> Path:
    """Prefer a user-provided Data directory next to the executable."""
    external = external_data_dir()
    if external.exists():
        return external
    return bundled_data_dir()


def resolve_db_path() -> Path:
    """Return the SQLite database location for the current runtime mode.

    Resolution order:
    1. Explicit override via the app-specific DB env var
    2. Compiled app shared database in the per-user app state directory
    3. Repo-local source database when no shared database exists yet
    """
    override = os.environ.get(DB_PATH_ENV_VAR, "").strip()
    if override:
        return Path(override).expanduser()

    if is_compiled():
        return user_state_dir(create=True) / DB_FILENAME

    return bundle_root() / "Data" / DB_FILENAME


def is_compiled() -> bool:
    """Return whether the application is running from a compiled binary."""
    return "__compiled__" in globals()


def user_state_dir(create: bool = True) -> Path:
    """Return the per-user application state directory.

    Set create=False to inspect the expected path without creating it.
    """
    base_dir = Path(os.environ.get("LOCALAPPDATA", executable_dir()))
    state_dir = base_dir / APP_DIR_NAME
    if create:
        state_dir.mkdir(parents=True, exist_ok=True)
    return state_dir

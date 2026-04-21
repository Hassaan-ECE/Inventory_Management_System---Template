"""Path and shared-root resolution helpers for shared-first sync."""

from __future__ import annotations

from pathlib import Path

from Code.sync._service_impl import (
    _require_shared_db_path,
    _resolve_local_db_path,
    _resolve_local_target,
    _resolve_shared_database_dir,
    _resolve_shared_db_path,
    _resolve_shared_root,
    shared_db_path,
    shared_dir,
)

__all__ = [
    "shared_dir",
    "shared_db_path",
    "_require_shared_db_path",
    "_resolve_local_db_path",
    "_resolve_local_target",
    "_resolve_shared_database_dir",
    "_resolve_shared_db_path",
    "_resolve_shared_root",
]

"""Public shared-sync facade with decomposed internal modules."""

from __future__ import annotations

from Code.sync._service_impl import shared_sync_enabled, sync_interval_ms, sync_local_from_shared, sync_local_with_shared
from Code.sync.contracts import RevisionInfo, SharedStatus, SyncResult
from Code.sync.mutations import (
    _bootstrap_shared_from_local_if_needed,
    _coerce_equipment,
    _get_local_equipment,
    _is_busy_error,
    _run_shared_import,
    _run_shared_mutation,
    _shared_connection,
    create_equipment,
    delete_equipment,
    import_database_into_shared,
    refresh_local_cache_from_shared_rows,
    run_excel_import,
    set_archived,
    toggle_verified,
    update_equipment,
)
from Code.sync.paths import (
    _require_shared_db_path,
    _resolve_local_db_path,
    _resolve_local_target,
    _resolve_shared_database_dir,
    _resolve_shared_db_path,
    _resolve_shared_root,
    shared_db_path,
    shared_dir,
)
from Code.sync.revision import (
    _ensure_numeric_revision,
    _increment_shared_revision,
    _parse_revision,
    _set_numeric_revision,
    check_revision,
    check_shared_status,
    initialize_client_sync,
)
from Code.sync.update_checks import UpdateInfo, check_for_update, update_checks_enabled

__all__ = [
    "RevisionInfo",
    "SharedStatus",
    "SyncResult",
    "UpdateInfo",
    "check_for_update",
    "check_revision",
    "check_shared_status",
    "create_equipment",
    "delete_equipment",
    "import_database_into_shared",
    "initialize_client_sync",
    "refresh_local_cache_from_shared_rows",
    "run_excel_import",
    "set_archived",
    "shared_db_path",
    "shared_dir",
    "shared_sync_enabled",
    "sync_interval_ms",
    "sync_local_from_shared",
    "sync_local_with_shared",
    "toggle_verified",
    "update_checks_enabled",
    "update_equipment",
]
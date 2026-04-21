"""Shared mutation/import orchestration helpers."""

from __future__ import annotations

import sqlite3
from typing import Any, Iterable, Mapping

from Code.db.database import replace_local_snapshot
from Code.sync._service_impl import (
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
    run_excel_import,
    set_archived,
    toggle_verified,
    update_equipment,
)


def refresh_local_cache_from_shared_rows(
    local_conn: sqlite3.Connection,
    *,
    equipment_rows: Iterable[Mapping[str, Any]],
    import_issue_rows: Iterable[Mapping[str, Any]],
    raw_cell_rows: Iterable[Mapping[str, Any]],
    revision: int | str,
    global_mutation_at: str = "",
) -> dict[str, int]:
    """Apply one shared snapshot payload to local cache in a single place."""
    return replace_local_snapshot(
        local_conn,
        equipment_rows,
        import_issue_rows,
        raw_cell_snapshot=raw_cell_rows,
        tombstone_snapshot=[],
        revision=str(revision),
        equipment_snapshot_hash="",
        import_issue_snapshot_hash="",
        global_mutation_at=global_mutation_at,
        clear_outbox=True,
        clear_applied_ops=True,
        commit=True,
    )


__all__ = [
    "create_equipment",
    "delete_equipment",
    "import_database_into_shared",
    "refresh_local_cache_from_shared_rows",
    "run_excel_import",
    "set_archived",
    "toggle_verified",
    "update_equipment",
    "_bootstrap_shared_from_local_if_needed",
    "_coerce_equipment",
    "_get_local_equipment",
    "_is_busy_error",
    "_run_shared_import",
    "_run_shared_mutation",
    "_shared_connection",
]

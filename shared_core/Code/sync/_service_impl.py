"""Shared-first sync facade for inventory apps that share a network database."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Mapping

from app_config import APP_CONFIG
from Code.db.database import (
    create_tables,
    delete_equipment as delete_equipment_local,
    fetch_equipment_snapshot,
    fetch_import_issue_snapshot,
    fetch_raw_cell_snapshot,
    get_all_equipment,
    get_connection,
    get_database_path,
    get_equipment_by_uuid,
    import_database_snapshot,
    insert_equipment,
    load_sync_state,
    replace_local_snapshot,
    set_sync_state,
    update_equipment as update_equipment_local,
)
from Code.db.models import Equipment
from Code.importer.pipeline import run_full_import_to_db, run_merge_import_to_db
from Code.sync.contracts import RevisionInfo, SharedStatus, SyncResult
from Code.sync.update_checks import UpdateInfo, check_for_update, update_checks_enabled
from Code.utils.runtime_paths import (
    resolve_db_path,
    shared_database_dir as runtime_shared_database_dir,
    shared_db_path as runtime_shared_db_path,
    shared_root_dir as runtime_shared_root_dir,
)

_UNAVAILABLE_MESSAGE = "Shared workspace unavailable. Viewing local cache only."
_BUSY_MESSAGE = "Shared workspace busy, retry in a moment."


def shared_sync_enabled() -> bool:
    """Return whether this app variant is configured to use shared sync."""
    return bool(getattr(APP_CONFIG, "enable_shared_sync", False))


def sync_interval_ms() -> int:
    """Return the configured automatic sync interval for this app."""
    value = getattr(APP_CONFIG, "auto_sync_interval_ms", 300000)
    try:
        interval_ms = int(value or 300000)
    except (TypeError, ValueError):
        interval_ms = 300000
    return max(5000, interval_ms)


def shared_dir(override_root: Path | None = None) -> Path | None:
    """Return the shared database directory for the active app variant."""
    return _resolve_shared_database_dir(override_root, create=False)


def shared_db_path(override_root: Path | None = None) -> Path | None:
    """Return the shared database path for the active app variant."""
    return _resolve_shared_db_path(override_root, create=False)


def initialize_client_sync(local_db_path: Path | str | sqlite3.Connection | None = None) -> SharedStatus:
    """Compatibility helper that reports current shared status for the local cache."""
    return check_shared_status(local_db_path)


def check_shared_status(
    local_db_path: Path | str | sqlite3.Connection | None = None,
    override_root: Path | None = None,
) -> SharedStatus:
    """Report whether the shared database is reachable for the current local cache."""
    del local_db_path
    if not shared_sync_enabled():
        return SharedStatus(message="Shared sync is disabled for this app.")

    root = _resolve_shared_root(override_root)
    if root is None:
        return SharedStatus(enabled=True, message="Shared sync path is not configured.")
    if not root.exists():
        return SharedStatus(enabled=True, message=_UNAVAILABLE_MESSAGE)

    shared_path = _resolve_shared_db_path(override_root, create=True)
    if shared_path is None:
        return SharedStatus(enabled=True, message="Shared sync paths could not be resolved.")

    try:
        conn = _shared_connection(shared_path)
        try:
            revision = _ensure_numeric_revision(conn, updated_by="status")
        finally:
            conn.close()
    except sqlite3.OperationalError as exc:
        if _is_busy_error(exc):
            return SharedStatus(enabled=True, shared_available=True, busy=True, message=_BUSY_MESSAGE)
        return SharedStatus(enabled=True, message=_UNAVAILABLE_MESSAGE)
    except (OSError, sqlite3.DatabaseError):
        return SharedStatus(enabled=True, message=_UNAVAILABLE_MESSAGE)

    return SharedStatus(
        enabled=True,
        shared_available=True,
        shared_revision=str(revision),
        message="Shared sync connected.",
    )


def check_revision(
    local_db_path: Path | str | sqlite3.Connection | None = None,
    override_root: Path | None = None,
) -> RevisionInfo:
    """Check whether the local cache is behind the shared authoritative revision."""
    if not shared_sync_enabled():
        return RevisionInfo(message="Shared sync is disabled for this app.")

    local_path, local_conn, should_close = _resolve_local_target(local_db_path)
    try:
        create_tables(local_conn)
        local_state = load_sync_state(local_conn)
        local_revision = _parse_revision(local_state.get("revision", ""))
    finally:
        if should_close:
            local_conn.close()

    root = _resolve_shared_root(override_root)
    if root is None or not root.exists():
        return RevisionInfo(
            enabled=True,
            shared_available=False,
            local_revision=str(local_revision),
            message=_UNAVAILABLE_MESSAGE,
        )

    shared_path = _resolve_shared_db_path(override_root, create=True)
    if shared_path is None:
        return RevisionInfo(
            enabled=True,
            shared_available=False,
            local_revision=str(local_revision),
            message=_UNAVAILABLE_MESSAGE,
        )

    try:
        shared_conn = _shared_connection(shared_path)
        try:
            shared_revision = _ensure_numeric_revision(shared_conn, updated_by="revision_check")
        finally:
            shared_conn.close()
    except sqlite3.OperationalError as exc:
        if _is_busy_error(exc):
            return RevisionInfo(
                enabled=True,
                shared_available=True,
                busy=True,
                local_revision=str(local_revision),
                message=_BUSY_MESSAGE,
            )
        return RevisionInfo(
            enabled=True,
            shared_available=False,
            local_revision=str(local_revision),
            message=_UNAVAILABLE_MESSAGE,
        )
    except (OSError, sqlite3.DatabaseError):
        return RevisionInfo(
            enabled=True,
            shared_available=False,
            local_revision=str(local_revision),
            message=_UNAVAILABLE_MESSAGE,
        )

    return RevisionInfo(
        enabled=True,
        shared_available=True,
        local_revision=str(local_revision),
        shared_revision=str(shared_revision),
        needs_sync=shared_revision > local_revision,
        message="Local snapshot is current." if shared_revision <= local_revision else "Shared data changed.",
    )


def sync_local_from_shared(
    local_db_path: Path | str | sqlite3.Connection | None = None,
    override_root: Path | None = None,
    *,
    force: bool = False,
) -> SyncResult:
    """Refresh the local cache from the shared authoritative database."""
    if not shared_sync_enabled():
        return SyncResult(message="Shared sync is disabled for this app.")

    local_path, local_conn, should_close = _resolve_local_target(local_db_path)
    try:
        create_tables(local_conn)
        local_revision = _parse_revision(load_sync_state(local_conn).get("revision", ""))
    except Exception:
        local_revision = 0

    root = _resolve_shared_root(override_root)
    if root is None or not root.exists():
        if should_close:
            local_conn.close()
        return SyncResult(
            enabled=True,
            local_revision=str(local_revision),
            message=_UNAVAILABLE_MESSAGE,
        )

    shared_path = _resolve_shared_db_path(override_root, create=True)
    if shared_path is None:
        if should_close:
            local_conn.close()
        return SyncResult(
            enabled=True,
            local_revision=str(local_revision),
            message=_UNAVAILABLE_MESSAGE,
        )

    try:
        bootstrap_revision = None
        if force:
            bootstrap_revision = _bootstrap_shared_from_local_if_needed(local_conn, shared_path)

        shared_conn = _shared_connection(shared_path)
        try:
            shared_revision = _ensure_numeric_revision(shared_conn, updated_by="sync")
            equipment_rows = fetch_equipment_snapshot(shared_conn)
            import_issue_rows = fetch_import_issue_snapshot(shared_conn)
            raw_cell_rows = fetch_raw_cell_snapshot(shared_conn)
            sync_state = load_sync_state(shared_conn)
        finally:
            shared_conn.close()

        if bootstrap_revision is not None:
            shared_revision = bootstrap_revision
            sync_state["revision"] = str(shared_revision)

        pulled = len(equipment_rows) + len(import_issue_rows) + len(raw_cell_rows)
        replace_local_snapshot(
            local_conn,
            equipment_rows,
            import_issue_rows,
            raw_cell_snapshot=raw_cell_rows,
            tombstone_snapshot=[],
            revision=str(shared_revision),
            equipment_snapshot_hash="",
            import_issue_snapshot_hash="",
            global_mutation_at=sync_state.get("global_mutation_at", ""),
            clear_outbox=True,
            clear_applied_ops=True,
            commit=True,
        )
        return SyncResult(
            enabled=True,
            shared_available=True,
            pulled=pulled,
            local_revision=str(shared_revision),
            shared_revision=str(shared_revision),
            message="Local snapshot refreshed from shared." if pulled else "Shared sync connected.",
        )
    except sqlite3.OperationalError as exc:
        if _is_busy_error(exc):
            return SyncResult(
                enabled=True,
                shared_available=True,
                busy=True,
                local_revision=str(local_revision),
                message=_BUSY_MESSAGE,
            )
        return SyncResult(
            enabled=True,
            local_revision=str(local_revision),
            message=_UNAVAILABLE_MESSAGE,
        )
    except (OSError, sqlite3.DatabaseError):
        return SyncResult(
            enabled=True,
            local_revision=str(local_revision),
            message=_UNAVAILABLE_MESSAGE,
        )
    finally:
        if should_close:
            local_conn.close()


def sync_local_with_shared(local_conn, override_root: Path | None = None) -> SyncResult:
    """Compatibility wrapper used by startup paths and tests."""
    if local_conn is None:
        return SyncResult(enabled=True, message="Local database connection is unavailable.")
    return sync_local_from_shared(local_conn, override_root=override_root, force=False)


def create_equipment(
    local_db_path: Path | str | sqlite3.Connection | None,
    equipment: Equipment | Mapping[str, Any],
    override_root: Path | None = None,
    *,
    refresh_local: bool = True,
) -> Equipment:
    """Create a record in the shared database and refresh the local cache."""
    eq = _coerce_equipment(equipment)

    def mutate(conn: sqlite3.Connection) -> None:
        insert_equipment(conn, eq, commit=False)

    _run_shared_mutation(local_db_path, mutate, override_root=override_root, refresh_local=refresh_local)
    refreshed = _get_local_equipment(local_db_path, eq.record_uuid)
    if refreshed is None:
        raise KeyError(f"Record not found after create: {eq.record_uuid}")
    return refreshed


def update_equipment(
    local_db_path: Path | str | sqlite3.Connection | None,
    equipment: Equipment | Mapping[str, Any],
    override_root: Path | None = None,
    *,
    refresh_local: bool = True,
) -> Equipment:
    """Update a shared record and refresh the local cache."""
    eq = _coerce_equipment(equipment)
    record_uuid = (eq.record_uuid or "").strip()
    if not record_uuid:
        raise ValueError("record_uuid is required for update.")

    def mutate(conn: sqlite3.Connection) -> None:
        existing = get_equipment_by_uuid(conn, record_uuid)
        if existing is None:
            raise KeyError(f"Unknown record_uuid: {record_uuid}")
        eq.record_id = existing.record_id
        update_equipment_local(conn, eq, commit=False)

    _run_shared_mutation(local_db_path, mutate, override_root=override_root, refresh_local=refresh_local)
    refreshed = _get_local_equipment(local_db_path, record_uuid)
    if refreshed is None:
        raise KeyError(f"Record not found after update: {record_uuid}")
    return refreshed


def delete_equipment(
    local_db_path: Path | str | sqlite3.Connection | None,
    record_uuid: str,
    override_root: Path | None = None,
    *,
    refresh_local: bool = True,
) -> None:
    """Delete a shared record and refresh the local cache."""
    normalized_uuid = (record_uuid or "").strip()
    if not normalized_uuid:
        raise ValueError("record_uuid is required for delete.")

    def mutate(conn: sqlite3.Connection) -> None:
        existing = get_equipment_by_uuid(conn, normalized_uuid)
        if existing is None or existing.record_id is None:
            raise KeyError(f"Unknown record_uuid: {normalized_uuid}")
        delete_equipment_local(conn, existing.record_id, commit=False)

    _run_shared_mutation(local_db_path, mutate, override_root=override_root, refresh_local=refresh_local)


def set_archived(
    local_db_path: Path | str | sqlite3.Connection | None,
    record_uuid: str,
    archived: bool,
    override_root: Path | None = None,
    *,
    refresh_local: bool = True,
) -> Equipment:
    """Archive or restore a shared record and refresh the local cache."""
    normalized_uuid = (record_uuid or "").strip()
    if not normalized_uuid:
        raise ValueError("record_uuid is required for archive changes.")

    def mutate(conn: sqlite3.Connection) -> None:
        existing = get_equipment_by_uuid(conn, normalized_uuid)
        if existing is None:
            raise KeyError(f"Unknown record_uuid: {normalized_uuid}")
        existing.is_archived = bool(archived)
        update_equipment_local(conn, existing, commit=False)

    _run_shared_mutation(local_db_path, mutate, override_root=override_root, refresh_local=refresh_local)
    refreshed = _get_local_equipment(local_db_path, normalized_uuid)
    if refreshed is None:
        raise KeyError(f"Record not found after archive update: {normalized_uuid}")
    return refreshed


def toggle_verified(
    local_db_path: Path | str | sqlite3.Connection | None,
    record_uuid: str,
    override_root: Path | None = None,
    *,
    refresh_local: bool = True,
) -> Equipment:
    """Toggle verification in the shared database and refresh the local cache."""
    normalized_uuid = (record_uuid or "").strip()
    if not normalized_uuid:
        raise ValueError("record_uuid is required for verification changes.")

    def mutate(conn: sqlite3.Connection) -> None:
        existing = get_equipment_by_uuid(conn, normalized_uuid)
        if existing is None:
            raise KeyError(f"Unknown record_uuid: {normalized_uuid}")
        existing.verified_in_survey = not bool(existing.verified_in_survey)
        update_equipment_local(conn, existing, commit=False)

    _run_shared_mutation(local_db_path, mutate, override_root=override_root, refresh_local=refresh_local)
    refreshed = _get_local_equipment(local_db_path, normalized_uuid)
    if refreshed is None:
        raise KeyError(f"Record not found after verify toggle: {normalized_uuid}")
    return refreshed


def run_excel_import(
    local_db_path: Path | str | sqlite3.Connection | None,
    data_dir: Path | str,
    override_root: Path | None = None,
    *,
    mode: str = "merge",
    refresh_local: bool = True,
    progress_callback=None,
) -> dict[str, int]:
    """Run an Excel import into the shared database and refresh the local cache."""
    local_path, local_conn, should_close = _resolve_local_target(local_db_path)
    del local_path
    shared_path = _require_shared_db_path(override_root)

    try:
        if mode == "full":
            stats = run_full_import_to_db(Path(data_dir), shared_path, progress_callback=progress_callback, use_wal=False)
        else:
            stats = run_merge_import_to_db(Path(data_dir), shared_path, progress_callback=progress_callback, use_wal=False)

        shared_conn = _shared_connection(shared_path)
        try:
            revision = _increment_shared_revision(shared_conn, "excel_import")
            equipment_rows = fetch_equipment_snapshot(shared_conn)
            import_issue_rows = fetch_import_issue_snapshot(shared_conn)
            raw_cell_rows = fetch_raw_cell_snapshot(shared_conn)
            sync_state = load_sync_state(shared_conn)
            shared_conn.commit()
        finally:
            shared_conn.close()

        if refresh_local:
            replace_local_snapshot(
                local_conn,
                equipment_rows,
                import_issue_rows,
                raw_cell_snapshot=raw_cell_rows,
                tombstone_snapshot=[],
                revision=str(revision),
                equipment_snapshot_hash="",
                import_issue_snapshot_hash="",
                global_mutation_at=sync_state.get("global_mutation_at", ""),
                clear_outbox=True,
                clear_applied_ops=True,
                commit=True,
            )
        return stats
    except sqlite3.OperationalError as exc:
        if _is_busy_error(exc):
            raise TimeoutError(_BUSY_MESSAGE) from exc
        raise ConnectionError(_UNAVAILABLE_MESSAGE) from exc
    except (OSError, sqlite3.DatabaseError) as exc:
        raise ConnectionError(_UNAVAILABLE_MESSAGE) from exc
    finally:
        if should_close:
            local_conn.close()


def import_database_into_shared(
    local_db_path: Path | str | sqlite3.Connection | None,
    source_db_path: Path | str,
    override_root: Path | None = None,
    *,
    refresh_local: bool = True,
) -> dict[str, int]:
    """Replace the shared snapshot from a selected DB file and refresh the local cache."""
    def mutate(conn: sqlite3.Connection) -> dict[str, int]:
        return import_database_snapshot(conn, Path(source_db_path))

    return _run_shared_import(
        local_db_path,
        mutate,
        override_root=override_root,
        refresh_local=refresh_local,
    )


def _run_shared_import(
    local_db_path: Path | str | sqlite3.Connection | None,
    importer,
    *,
    override_root: Path | None,
    refresh_local: bool,
) -> dict[str, int]:
    local_path, local_conn, should_close = _resolve_local_target(local_db_path)
    del local_path
    shared_path = _require_shared_db_path(override_root)

    try:
        shared_conn = _shared_connection(shared_path)
        try:
            stats = importer(shared_conn)
            revision = _increment_shared_revision(shared_conn, "database_import")
            equipment_rows = fetch_equipment_snapshot(shared_conn)
            import_issue_rows = fetch_import_issue_snapshot(shared_conn)
            raw_cell_rows = fetch_raw_cell_snapshot(shared_conn)
            sync_state = load_sync_state(shared_conn)
            shared_conn.commit()
        finally:
            shared_conn.close()

        if refresh_local:
            replace_local_snapshot(
                local_conn,
                equipment_rows,
                import_issue_rows,
                raw_cell_snapshot=raw_cell_rows,
                tombstone_snapshot=[],
                revision=str(revision),
                equipment_snapshot_hash="",
                import_issue_snapshot_hash="",
                global_mutation_at=sync_state.get("global_mutation_at", ""),
                clear_outbox=True,
                clear_applied_ops=True,
                commit=True,
            )
        return stats
    except sqlite3.OperationalError as exc:
        if _is_busy_error(exc):
            raise TimeoutError(_BUSY_MESSAGE) from exc
        raise ConnectionError(_UNAVAILABLE_MESSAGE) from exc
    except (OSError, sqlite3.DatabaseError) as exc:
        raise ConnectionError(_UNAVAILABLE_MESSAGE) from exc
    finally:
        if should_close:
            local_conn.close()


def _run_shared_mutation(
    local_db_path: Path | str | sqlite3.Connection | None,
    mutate,
    *,
    override_root: Path | None,
    refresh_local: bool,
) -> None:
    local_path, local_conn, should_close = _resolve_local_target(local_db_path)
    del local_path
    shared_path = _require_shared_db_path(override_root)

    try:
        shared_conn = _shared_connection(shared_path)
        try:
            shared_conn.execute("BEGIN IMMEDIATE")
            mutate(shared_conn)
            revision = _increment_shared_revision(shared_conn, APP_CONFIG.display_name)
            equipment_rows = fetch_equipment_snapshot(shared_conn)
            import_issue_rows = fetch_import_issue_snapshot(shared_conn)
            raw_cell_rows = fetch_raw_cell_snapshot(shared_conn)
            sync_state = load_sync_state(shared_conn)
            shared_conn.commit()
        except Exception:
            if shared_conn.in_transaction:
                shared_conn.rollback()
            raise
        finally:
            shared_conn.close()

        if refresh_local:
            replace_local_snapshot(
                local_conn,
                equipment_rows,
                import_issue_rows,
                raw_cell_snapshot=raw_cell_rows,
                tombstone_snapshot=[],
                revision=str(revision),
                equipment_snapshot_hash="",
                import_issue_snapshot_hash="",
                global_mutation_at=sync_state.get("global_mutation_at", ""),
                clear_outbox=True,
                clear_applied_ops=True,
                commit=True,
            )
    except sqlite3.OperationalError as exc:
        if _is_busy_error(exc):
            raise TimeoutError(_BUSY_MESSAGE) from exc
        raise ConnectionError(_UNAVAILABLE_MESSAGE) from exc
    except (OSError, sqlite3.DatabaseError) as exc:
        raise ConnectionError(_UNAVAILABLE_MESSAGE) from exc
    finally:
        if should_close:
            local_conn.close()


def _resolve_local_target(
    local_db_path: Path | str | sqlite3.Connection | None,
) -> tuple[Path, sqlite3.Connection, bool]:
    if isinstance(local_db_path, sqlite3.Connection):
        create_tables(local_db_path)
        path = get_database_path(local_db_path)
        if path is None:
            raise RuntimeError("Local database path is unavailable.")
        return path, local_db_path, False

    path = _resolve_local_db_path(local_db_path)
    conn = get_connection(path)
    create_tables(conn)
    return path, conn, True


def _resolve_local_db_path(local_db_path: Path | str | None) -> Path:
    if local_db_path is None:
        return resolve_db_path()
    return Path(local_db_path).expanduser().resolve()


def _resolve_shared_root(override_root: Path | None) -> Path | None:
    if override_root is not None:
        return Path(override_root).expanduser().resolve()
    return runtime_shared_root_dir()


def _resolve_shared_database_dir(override_root: Path | None, *, create: bool) -> Path | None:
    if override_root is not None:
        directory = Path(override_root).expanduser().resolve() / "shared"
        if create:
            directory.mkdir(parents=True, exist_ok=True)
        return directory
    return runtime_shared_database_dir(create=create)


def _resolve_shared_db_path(override_root: Path | None, *, create: bool) -> Path | None:
    if override_root is not None:
        filename = getattr(APP_CONFIG, "shared_db_filename", "").strip()
        if not filename:
            return None
        directory = _resolve_shared_database_dir(override_root, create=create)
        if directory is None:
            return None
        return directory / filename
    if create:
        directory = runtime_shared_database_dir(create=True)
        filename = getattr(APP_CONFIG, "shared_db_filename", "").strip()
        if directory is None or not filename:
            return None
        return directory / filename
    return runtime_shared_db_path()


def _require_shared_db_path(override_root: Path | None) -> Path:
    root = _resolve_shared_root(override_root)
    if root is None or not root.exists():
        raise ConnectionError(_UNAVAILABLE_MESSAGE)
    shared_path = _resolve_shared_db_path(override_root, create=True)
    if shared_path is None:
        raise ConnectionError(_UNAVAILABLE_MESSAGE)
    return shared_path


def _shared_connection(shared_path: Path) -> sqlite3.Connection:
    conn = get_connection(shared_path, use_wal=False)
    conn.execute("PRAGMA journal_mode=DELETE")
    conn.execute("PRAGMA synchronous=FULL")
    conn.execute("PRAGMA busy_timeout = 2000")
    create_tables(conn)
    return conn


def _bootstrap_shared_from_local_if_needed(local_conn: sqlite3.Connection, shared_path: Path) -> int | None:
    local_rows = get_all_equipment(local_conn, archived="all")
    if not local_rows:
        return None

    shared_conn = _shared_connection(shared_path)
    try:
        current_revision = _parse_revision(load_sync_state(shared_conn).get("revision", ""))
        shared_rows = get_all_equipment(shared_conn, archived="all")
        if current_revision > 0 or shared_rows:
            return None

        equipment_snapshot = fetch_equipment_snapshot(local_conn)
        import_issue_snapshot = fetch_import_issue_snapshot(local_conn)
        raw_cell_snapshot = fetch_raw_cell_snapshot(local_conn)

        replace_local_snapshot(
            shared_conn,
            equipment_snapshot,
            import_issue_snapshot,
            raw_cell_snapshot=raw_cell_snapshot,
            tombstone_snapshot=[],
            revision="1",
            equipment_snapshot_hash="",
            import_issue_snapshot_hash="",
            global_mutation_at="",
            clear_outbox=True,
            clear_applied_ops=True,
            commit=True,
        )
        _set_numeric_revision(shared_conn, 1, "bootstrap", commit=True)
        return 1
    finally:
        shared_conn.close()


def _ensure_numeric_revision(conn: sqlite3.Connection, updated_by: str) -> int:
    state = load_sync_state(conn)
    revision = _parse_revision(state.get("revision", ""))
    if str(state.get("revision", "")).strip().isdigit():
        return revision

    row = conn.execute("SELECT COUNT(*) FROM equipment").fetchone()
    record_count = int(row[0] if row is not None else 0)
    normalized_revision = 1 if record_count > 0 else 0
    _set_numeric_revision(conn, normalized_revision, updated_by, commit=True)
    return normalized_revision


def _increment_shared_revision(conn: sqlite3.Connection, updated_by: str) -> int:
    current_revision = _ensure_numeric_revision(conn, updated_by)
    next_revision = current_revision + 1
    _set_numeric_revision(conn, next_revision, updated_by, commit=False)
    return next_revision


def _set_numeric_revision(conn: sqlite3.Connection, revision: int, updated_by: str, *, commit: bool) -> None:
    set_sync_state(
        conn,
        revision=str(max(int(revision), 0)),
        equipment_snapshot_hash="",
        import_issue_snapshot_hash="",
        global_mutation_at="",
        commit=commit,
    )


def _parse_revision(value: Any) -> int:
    try:
        return max(int(str(value or "").strip()), 0)
    except (TypeError, ValueError):
        return 0


def _coerce_equipment(equipment: Equipment | Mapping[str, Any]) -> Equipment:
    if isinstance(equipment, Equipment):
        return equipment

    eq = Equipment()
    for field_name, value in dict(equipment).items():
        if hasattr(eq, field_name):
            setattr(eq, field_name, value)
    return eq


def _get_local_equipment(
    local_db_path: Path | str | sqlite3.Connection | None,
    record_uuid: str,
) -> Equipment | None:
    _, conn, should_close = _resolve_local_target(local_db_path)
    try:
        return get_equipment_by_uuid(conn, record_uuid)
    finally:
        if should_close:
            conn.close()


def _is_busy_error(exc: BaseException) -> bool:
    return "locked" in str(exc).lower() or "busy" in str(exc).lower()

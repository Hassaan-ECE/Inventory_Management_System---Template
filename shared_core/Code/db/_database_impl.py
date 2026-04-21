"""SQLite database implementation for the shared Lab Inventory runtime."""

import json
import sqlite3
import string
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional

from app_config import APP_CONFIG
from Code.db.models import Equipment, ImportIssue, RawCell
from Code.utils.runtime_paths import resolve_db_path

DB_PATH = resolve_db_path()
_SEARCH_TEXT_FIELDS = (
    "asset_number",
    "serial_number",
    "manufacturer",
    "manufacturer_raw",
    "model",
    "description",
    "project_name",
    "links",
    "location",
    "assigned_to",
    "notes",
    "condition",
    "calibration_status",
    "lifecycle_status",
    "working_status",
    "calibration_vendor",
    "rental_vendor",
)
_EQUIPMENT_COPY_COLUMNS = (
    "record_id",
    "record_uuid",
    "asset_number",
    "serial_number",
    "manufacturer",
    "manufacturer_raw",
    "model",
    "description",
    "qty",
    "location",
    "assigned_to",
    "ownership_type",
    "rental_vendor",
    "rental_cost_monthly",
    "calibration_status",
    "last_calibration_date",
    "calibration_due_date",
    "calibration_vendor",
    "calibration_cost",
    "lifecycle_status",
    "working_status",
    "condition",
    "acquired_date",
    "estimated_age_years",
    "age_basis",
    "verified_in_survey",
    "blue_dot_ref",
    "project_name",
    "picture_path",
    "links",
    "notes",
    "manual_entry",
    "is_archived",
    "source_refs",
    "created_at",
    "updated_at",
)
_OPTIONAL_ATTACHED_COLUMN_DEFAULTS = {
    "equipment": {
        "record_uuid": "''",
        "project_name": "''",
        "picture_path": "''",
        "links": "''",
        "is_archived": "0",
    },
}
_RAW_CELL_COPY_COLUMNS = (
    "id",
    "source_file",
    "source_sheet",
    "row_number",
    "column_number",
    "cell_address",
    "cell_value",
    "row_preview",
)
_IMPORT_ISSUE_COPY_COLUMNS = (
    "id",
    "issue_type",
    "source_file",
    "source_sheet",
    "source_row",
    "asset_number",
    "serial_number",
    "summary",
    "raw_data",
    "resolution_status",
    "created_at",
)
_CLIENT_IDENTITY_ROW_ID = 1
_SYNC_STATE_ROW_ID = 1
_SYNC_STATE_DEFAULTS = {
    "revision": "",
    "equipment_snapshot_hash": "",
    "import_issue_snapshot_hash": "",
    "global_mutation_at": "",
}
_EQUIPMENT_TOMBSTONE_COPY_COLUMNS = (
    "record_uuid",
    "deleted_at",
    "deleted_by_client_id",
    "op_id",
)
_OPTIONAL_SNAPSHOT_COLUMN_DEFAULTS = {
    "equipment": {
        "record_uuid": "",
        "project_name": "",
        "picture_path": "",
        "links": "",
        "is_archived": 0,
    },
    "equipment_tombstones": {
        "deleted_by_client_id": "",
        "op_id": "",
    },
}
_OUTBOX_STATUSES = {"pending", "inflight", "applied", "superseded", "failed"}
_UNSET = object()


def get_connection(db_path: Optional[Path] = None, use_wal: bool = True) -> sqlite3.Connection:
    """Get a SQLite connection with WAL mode and foreign keys enabled."""
    path = db_path or DB_PATH
    conn = sqlite3.connect(str(path), timeout=5.0)
    conn.execute("PRAGMA journal_mode=WAL" if use_wal else "PRAGMA journal_mode=DELETE")
    conn.execute("PRAGMA busy_timeout = 5000")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    return conn


def create_tables(conn: sqlite3.Connection) -> None:
    """Create all tables if they don't exist."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS equipment (
            record_id          INTEGER PRIMARY KEY AUTOINCREMENT,
            record_uuid        TEXT DEFAULT '',
            asset_number       TEXT DEFAULT '',
            serial_number      TEXT DEFAULT '',
            manufacturer       TEXT DEFAULT '',
            manufacturer_raw   TEXT DEFAULT '',
            model              TEXT DEFAULT '',
            description        TEXT DEFAULT '',
            qty                REAL,

            location           TEXT DEFAULT '',
            assigned_to        TEXT DEFAULT '',
            ownership_type     TEXT DEFAULT 'owned',
            rental_vendor      TEXT DEFAULT '',
            rental_cost_monthly REAL,

            calibration_status TEXT DEFAULT 'unknown',
            last_calibration_date TEXT DEFAULT '',
            calibration_due_date  TEXT DEFAULT '',
            calibration_vendor TEXT DEFAULT '',
            calibration_cost   REAL,

            lifecycle_status   TEXT DEFAULT 'active',
            working_status     TEXT DEFAULT 'unknown',
            condition          TEXT DEFAULT '',

            acquired_date      TEXT DEFAULT '',
            estimated_age_years REAL,
            age_basis          TEXT DEFAULT 'unknown',
            verified_in_survey INTEGER DEFAULT 0,
            blue_dot_ref       TEXT DEFAULT '',

            project_name       TEXT DEFAULT '',
            picture_path       TEXT DEFAULT '',
            links              TEXT DEFAULT '',
            notes              TEXT DEFAULT '',
            manual_entry       INTEGER DEFAULT 0,
            is_archived        INTEGER DEFAULT 0,
            source_refs        TEXT DEFAULT '[]',
            created_at         TEXT DEFAULT (datetime('now')),
            updated_at         TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS raw_cells (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            source_file   TEXT,
            source_sheet  TEXT,
            row_number    INTEGER,
            column_number INTEGER,
            cell_address  TEXT,
            cell_value    TEXT,
            row_preview   TEXT
        );

        CREATE TABLE IF NOT EXISTS import_issues (
            id                 INTEGER PRIMARY KEY AUTOINCREMENT,
            issue_type         TEXT,
            source_file        TEXT,
            source_sheet       TEXT,
            source_row         INTEGER,
            asset_number       TEXT DEFAULT '',
            serial_number      TEXT DEFAULT '',
            summary            TEXT,
            raw_data           TEXT DEFAULT '{}',
            resolution_status  TEXT DEFAULT 'unresolved',
            created_at         TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS sync_state (
            id                         INTEGER PRIMARY KEY CHECK (id = 1),
            revision                   TEXT DEFAULT '',
            equipment_snapshot_hash    TEXT DEFAULT '',
            import_issue_snapshot_hash TEXT DEFAULT '',
            global_mutation_at         TEXT DEFAULT '',
            updated_at                 TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS client_identity (
            id         INTEGER PRIMARY KEY CHECK (id = 1),
            client_id  TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS sync_outbox (
            op_id            TEXT PRIMARY KEY,
            client_id        TEXT DEFAULT '',
            op_type          TEXT DEFAULT '',
            record_uuid      TEXT DEFAULT '',
            mutation_ts      TEXT DEFAULT '',
            payload_json     TEXT DEFAULT '{}',
            artifact_path    TEXT DEFAULT '',
            status           TEXT DEFAULT 'pending',
            attempt_count    INTEGER DEFAULT 0,
            last_error       TEXT DEFAULT '',
            created_at       TEXT DEFAULT (datetime('now')),
            last_attempt_at  TEXT DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS applied_ops (
            op_id       TEXT PRIMARY KEY,
            client_id   TEXT DEFAULT '',
            op_type     TEXT DEFAULT '',
            record_uuid TEXT DEFAULT '',
            mutation_ts TEXT DEFAULT '',
            applied_at  TEXT DEFAULT (datetime('now')),
            result      TEXT DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS equipment_tombstones (
            record_uuid           TEXT PRIMARY KEY,
            deleted_at            TEXT DEFAULT '',
            deleted_by_client_id  TEXT DEFAULT '',
            op_id                 TEXT DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS record_sync_state (
            record_uuid       TEXT PRIMARY KEY,
            last_synced_hash  TEXT DEFAULT '',
            synced_at         TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS sync_conflicts (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            record_uuid       TEXT DEFAULT '',
            local_hash        TEXT DEFAULT '',
            shared_hash       TEXT DEFAULT '',
            last_synced_hash  TEXT DEFAULT '',
            summary           TEXT DEFAULT '',
            created_at        TEXT DEFAULT (datetime('now')),
            resolved          INTEGER DEFAULT 0
        );

        CREATE INDEX IF NOT EXISTS idx_equipment_asset ON equipment(asset_number);
        CREATE INDEX IF NOT EXISTS idx_equipment_serial ON equipment(serial_number);
        CREATE INDEX IF NOT EXISTS idx_equipment_lifecycle ON equipment(lifecycle_status);
        CREATE INDEX IF NOT EXISTS idx_equipment_cal ON equipment(calibration_status);
        CREATE INDEX IF NOT EXISTS idx_raw_cells_value ON raw_cells(cell_value);
        CREATE INDEX IF NOT EXISTS idx_import_issues_status ON import_issues(resolution_status);
        CREATE INDEX IF NOT EXISTS idx_sync_conflicts_resolved ON sync_conflicts(resolved);
        CREATE INDEX IF NOT EXISTS idx_sync_outbox_status_created ON sync_outbox(status, created_at);
        CREATE INDEX IF NOT EXISTS idx_sync_outbox_record_uuid ON sync_outbox(record_uuid);
        CREATE INDEX IF NOT EXISTS idx_applied_ops_applied_at ON applied_ops(applied_at);
        CREATE INDEX IF NOT EXISTS idx_applied_ops_record_uuid ON applied_ops(record_uuid);
        CREATE INDEX IF NOT EXISTS idx_equipment_tombstones_deleted_at ON equipment_tombstones(deleted_at);
    """)
    conn.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS equipment_search
        USING fts5(
            record_id UNINDEXED,
            search_text,
            tokenize='trigram'
        )
    """)
    _ensure_equipment_column(conn, "record_uuid", "TEXT DEFAULT ''")
    _ensure_equipment_column(conn, "project_name", "TEXT DEFAULT ''")
    _ensure_equipment_column(conn, "picture_path", "TEXT DEFAULT ''")
    _ensure_equipment_column(conn, "links", "TEXT DEFAULT ''")
    _ensure_equipment_column(conn, "is_archived", "INTEGER DEFAULT 0")
    _ensure_sync_state_table(conn)
    _ensure_client_identity_table(conn)
    _ensure_sync_outbox_table(conn)
    _ensure_applied_ops_table(conn)
    _ensure_equipment_tombstones_table(conn)
    _ensure_equipment_record_uuids(conn)
    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_equipment_record_uuid ON equipment(record_uuid)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_equipment_archived ON equipment(is_archived)")
    _ensure_equipment_search_index(conn)
    conn.commit()


def get_database_path(conn: sqlite3.Connection) -> Optional[Path]:
    """Return the primary database file path for an open connection."""
    rows = conn.execute("PRAGMA database_list").fetchall()
    for row in rows:
        name = row["name"] if isinstance(row, sqlite3.Row) else row[1]
        file_path = row["file"] if isinstance(row, sqlite3.Row) else row[2]
        if name == "main" and file_path:
            return Path(file_path)
    return None


def load_sync_state(conn: sqlite3.Connection) -> dict[str, str]:
    """Load the singleton authoritative sync-state row."""
    _ensure_sync_state_table(conn)
    row = conn.execute(
        """
        SELECT revision, equipment_snapshot_hash, import_issue_snapshot_hash, global_mutation_at, updated_at
        FROM sync_state
        WHERE id=?
        """,
        (_SYNC_STATE_ROW_ID,),
    ).fetchone()
    if row is None:
        return {
            "revision": _SYNC_STATE_DEFAULTS["revision"],
            "equipment_snapshot_hash": _SYNC_STATE_DEFAULTS["equipment_snapshot_hash"],
            "import_issue_snapshot_hash": _SYNC_STATE_DEFAULTS["import_issue_snapshot_hash"],
            "global_mutation_at": _SYNC_STATE_DEFAULTS["global_mutation_at"],
            "updated_at": "",
        }

    return {
        "revision": row["revision"] or "",
        "equipment_snapshot_hash": row["equipment_snapshot_hash"] or "",
        "import_issue_snapshot_hash": row["import_issue_snapshot_hash"] or "",
        "global_mutation_at": row["global_mutation_at"] or "",
        "updated_at": row["updated_at"] or "",
    }


def set_sync_state(
    conn: sqlite3.Connection,
    revision: Optional[str] = None,
    equipment_snapshot_hash: Optional[str] = None,
    import_issue_snapshot_hash: Optional[str] = None,
    global_mutation_at: Optional[str] = None,
    updated_at: Optional[str] = None,
    commit: bool = True,
) -> dict[str, str]:
    """Upsert authoritative sync-state metadata in the singleton row."""
    current = load_sync_state(conn)
    next_revision = current["revision"] if revision is None else str(revision)
    next_equipment_hash = (
        current["equipment_snapshot_hash"]
        if equipment_snapshot_hash is None
        else str(equipment_snapshot_hash)
    )
    next_issue_hash = (
        current["import_issue_snapshot_hash"]
        if import_issue_snapshot_hash is None
        else str(import_issue_snapshot_hash)
    )
    next_global_mutation_at = (
        current["global_mutation_at"]
        if global_mutation_at is None
        else str(global_mutation_at)
    )

    if updated_at is None:
        conn.execute(
            """
            INSERT INTO sync_state (
                id, revision, equipment_snapshot_hash, import_issue_snapshot_hash, global_mutation_at, updated_at
            ) VALUES (
                ?, ?, ?, ?, ?, datetime('now')
            )
            ON CONFLICT(id) DO UPDATE SET
                revision=excluded.revision,
                equipment_snapshot_hash=excluded.equipment_snapshot_hash,
                import_issue_snapshot_hash=excluded.import_issue_snapshot_hash,
                global_mutation_at=excluded.global_mutation_at,
                updated_at=datetime('now')
            """,
            (_SYNC_STATE_ROW_ID, next_revision, next_equipment_hash, next_issue_hash, next_global_mutation_at),
        )
    else:
        conn.execute(
            """
            INSERT INTO sync_state (
                id, revision, equipment_snapshot_hash, import_issue_snapshot_hash, global_mutation_at, updated_at
            ) VALUES (
                ?, ?, ?, ?, ?, ?
            )
            ON CONFLICT(id) DO UPDATE SET
                revision=excluded.revision,
                equipment_snapshot_hash=excluded.equipment_snapshot_hash,
                import_issue_snapshot_hash=excluded.import_issue_snapshot_hash,
                global_mutation_at=excluded.global_mutation_at,
                updated_at=excluded.updated_at
            """,
            (
                _SYNC_STATE_ROW_ID,
                next_revision,
                next_equipment_hash,
                next_issue_hash,
                next_global_mutation_at,
                str(updated_at),
            ),
        )

    if commit:
        conn.commit()
    return load_sync_state(conn)


def get_sync_state(conn: sqlite3.Connection) -> dict[str, str]:
    """Return the singleton sync-state row using getter-style naming."""
    return load_sync_state(conn)


def ensure_client_identity(conn: sqlite3.Connection, commit: bool = True) -> str:
    """Return this database's stable client identifier, creating one if needed."""
    _ensure_client_identity_table(conn)
    row = conn.execute("SELECT client_id FROM client_identity WHERE id=?", (_CLIENT_IDENTITY_ROW_ID,)).fetchone()
    client_id = ""
    if row is not None:
        client_id = str(row["client_id"] if hasattr(row, "keys") else row[0] or "").strip()
    if client_id:
        return client_id

    client_id = uuid.uuid4().hex
    conn.execute(
        """
        INSERT INTO client_identity (id, client_id, created_at)
        VALUES (?, ?, datetime('now'))
        ON CONFLICT(id) DO UPDATE SET client_id=excluded.client_id
        """,
        (_CLIENT_IDENTITY_ROW_ID, client_id),
    )
    if commit:
        conn.commit()
    return client_id


def enqueue_outbox_operation(
    conn: sqlite3.Connection,
    op_type: str,
    *,
    record_uuid: str = "",
    mutation_ts: str = "",
    payload_json: str = "{}",
    artifact_path: str = "",
    status: str = "pending",
    client_id: Optional[str] = None,
    op_id: Optional[str] = None,
    commit: bool = True,
) -> str:
    """Insert a persistent sync operation into the local outbox."""
    _ensure_sync_outbox_table(conn)
    normalized_status = status if status in _OUTBOX_STATUSES else "pending"
    resolved_client_id = client_id or ensure_client_identity(conn, commit=False)
    resolved_op_id = (op_id or uuid.uuid4().hex).strip() or uuid.uuid4().hex
    conn.execute(
        """
        INSERT INTO sync_outbox (
            op_id, client_id, op_type, record_uuid, mutation_ts, payload_json,
            artifact_path, status, attempt_count, last_error, created_at, last_attempt_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, '', datetime('now'), '')
        """,
        (
            resolved_op_id,
            resolved_client_id,
            str(op_type or "").strip(),
            str(record_uuid or "").strip(),
            str(mutation_ts or "").strip(),
            str(payload_json or "{}"),
            str(artifact_path or "").strip(),
            normalized_status,
        ),
    )
    if commit:
        conn.commit()
    return resolved_op_id


def list_outbox_operations(
    conn: sqlite3.Connection,
    statuses: Iterable[str] = ("pending", "failed"),
) -> list[dict[str, Any]]:
    """Return ordered outbox operations filtered by status."""
    _ensure_sync_outbox_table(conn)
    normalized = [str(value).strip() for value in statuses if str(value).strip()]
    if not normalized:
        normalized = ["pending"]
    placeholders = ", ".join("?" for _ in normalized)
    rows = conn.execute(
        f"""
        SELECT op_id, client_id, op_type, record_uuid, mutation_ts, payload_json,
               artifact_path, status, attempt_count, last_error, created_at, last_attempt_at
        FROM sync_outbox
        WHERE status IN ({placeholders})
        ORDER BY created_at, op_id
        """,
        tuple(normalized),
    ).fetchall()
    return [dict(row) for row in rows]


def count_pending_outbox_operations(conn: sqlite3.Connection) -> int:
    """Return how many queued sync operations still need replay."""
    _ensure_sync_outbox_table(conn)
    row = conn.execute(
        "SELECT COUNT(*) FROM sync_outbox WHERE status IN ('pending', 'failed')"
    ).fetchone()
    return int(row[0] if row is not None else 0)


def get_outbox_operation(conn: sqlite3.Connection, op_id: str) -> Optional[dict[str, Any]]:
    """Return a single outbox operation by identifier."""
    _ensure_sync_outbox_table(conn)
    normalized_op_id = str(op_id or "").strip()
    if not normalized_op_id:
        return None
    row = conn.execute(
        """
        SELECT op_id, client_id, op_type, record_uuid, mutation_ts, payload_json,
               artifact_path, status, attempt_count, last_error, created_at, last_attempt_at
        FROM sync_outbox
        WHERE op_id=?
        """,
        (normalized_op_id,),
    ).fetchone()
    return _normalize_outbox_row(row) if row is not None else None


def get_outbox_op(conn: sqlite3.Connection, op_id: str) -> Optional[dict[str, Any]]:
    """Getter-style alias for reading an outbox row."""
    return get_outbox_operation(conn, op_id)


def enqueue_outbox_op(
    conn: sqlite3.Connection,
    op_type: str,
    *,
    record_uuid: str = "",
    mutation_ts: str = "",
    payload: Any = None,
    artifact_path: str = "",
    status: str = "pending",
    client_id: Optional[str] = None,
    op_id: Optional[str] = None,
    commit: bool = True,
) -> dict[str, Any]:
    """Insert a persistent sync operation and return the stored row."""
    resolved_op_id = enqueue_outbox_operation(
        conn,
        op_type,
        record_uuid=record_uuid,
        mutation_ts=mutation_ts,
        payload_json=_json_dumps(payload, default="{}"),
        artifact_path=artifact_path,
        status=status,
        client_id=client_id,
        op_id=op_id,
        commit=commit,
    )
    stored = get_outbox_operation(conn, resolved_op_id)
    return stored or {"op_id": resolved_op_id}


def list_outbox_ops(
    conn: sqlite3.Connection,
    statuses: Optional[Any] = None,
    limit: Optional[int] = None,
) -> list[dict[str, Any]]:
    """List queued outbox operations with parsed payloads."""
    if statuses is None:
        selected_statuses: Iterable[str] = ("pending", "failed")
    elif isinstance(statuses, str):
        selected_statuses = (statuses,)
    else:
        selected_statuses = statuses

    rows = list_outbox_operations(conn, statuses=selected_statuses)
    if limit is not None:
        rows = rows[: max(int(limit), 0)]
    return [_normalize_outbox_row(row) for row in rows]


def update_outbox_op(
    conn: sqlite3.Connection,
    op_id: str,
    *,
    status: Optional[str] = None,
    last_error: Optional[str] = None,
    increment_attempt: bool = False,
    payload: Any = _UNSET,
    artifact_path: Any = _UNSET,
    mutation_ts: Any = _UNSET,
    commit: bool = True,
) -> Optional[dict[str, Any]]:
    """Update an outbox operation and return the persisted row."""
    _ensure_sync_outbox_table(conn)
    normalized_op_id = str(op_id or "").strip()
    if not normalized_op_id:
        return None

    assignments: list[str] = []
    params: list[Any] = []

    if status is not None:
        normalized_status = status if status in _OUTBOX_STATUSES else "pending"
        assignments.append("status=?")
        params.append(normalized_status)
    if last_error is not None:
        assignments.append("last_error=?")
        params.append(str(last_error or ""))
    if payload is not _UNSET:
        assignments.append("payload_json=?")
        params.append(_json_dumps(payload, default="{}"))
    if artifact_path is not _UNSET:
        assignments.append("artifact_path=?")
        params.append(str(artifact_path or "").strip())
    if mutation_ts is not _UNSET:
        assignments.append("mutation_ts=?")
        params.append(str(mutation_ts or "").strip())
    if increment_attempt:
        assignments.append("attempt_count = attempt_count + 1")
        assignments.append("last_attempt_at=datetime('now')")
    elif status is not None or last_error is not None:
        assignments.append("last_attempt_at=datetime('now')")

    if not assignments:
        return get_outbox_operation(conn, normalized_op_id)

    conn.execute(
        f"UPDATE sync_outbox SET {', '.join(assignments)} WHERE op_id=?",
        (*params, normalized_op_id),
    )
    if commit:
        conn.commit()
    return get_outbox_operation(conn, normalized_op_id)


def delete_outbox_op(conn: sqlite3.Connection, op_id: str, commit: bool = True) -> bool:
    """Delete a queued outbox operation."""
    _ensure_sync_outbox_table(conn)
    cur = conn.execute("DELETE FROM sync_outbox WHERE op_id=?", (str(op_id or "").strip(),))
    if commit:
        conn.commit()
    return cur.rowcount > 0


def update_outbox_operation_status(
    conn: sqlite3.Connection,
    op_id: str,
    status: str,
    *,
    last_error: str = "",
    increment_attempt: bool = False,
    commit: bool = True,
) -> None:
    """Update an outbox operation's replay state."""
    _ensure_sync_outbox_table(conn)
    normalized_status = status if status in _OUTBOX_STATUSES else "pending"
    attempt_sql = "attempt_count = attempt_count + 1," if increment_attempt else ""
    conn.execute(
        f"""
        UPDATE sync_outbox
        SET status=?,
            {attempt_sql}
            last_error=?,
            last_attempt_at=datetime('now')
        WHERE op_id=?
        """,
        (normalized_status, str(last_error or ""), str(op_id or "").strip()),
    )
    if commit:
        conn.commit()


def mark_outbox_operation_applied(conn: sqlite3.Connection, op_id: str, result: str = "", commit: bool = True) -> None:
    """Mark an outbox operation as fully applied."""
    update_outbox_operation_status(conn, op_id, "applied", last_error=result, increment_attempt=True, commit=commit)


def mark_outbox_operation_superseded(
    conn: sqlite3.Connection,
    op_id: str,
    result: str = "",
    commit: bool = True,
) -> None:
    """Mark an outbox operation as superseded by a newer shared mutation."""
    update_outbox_operation_status(
        conn,
        op_id,
        "superseded",
        last_error=result,
        increment_attempt=True,
        commit=commit,
    )


def mark_outbox_operation_pending(
    conn: sqlite3.Connection,
    op_id: str,
    error: str = "",
    *,
    increment_attempt: bool = False,
    commit: bool = True,
) -> None:
    """Return an outbox operation to the pending state."""
    update_outbox_operation_status(
        conn,
        op_id,
        "pending",
        last_error=error,
        increment_attempt=increment_attempt,
        commit=commit,
    )


def record_applied_operation(
    conn: sqlite3.Connection,
    op_id: str,
    client_id: str,
    op_type: str,
    record_uuid: str,
    mutation_ts: str,
    result: str = "",
    commit: bool = True,
) -> None:
    """Persist that a replayed operation has already been applied on shared."""
    _ensure_applied_ops_table(conn)
    conn.execute(
        """
        INSERT INTO applied_ops (op_id, client_id, op_type, record_uuid, mutation_ts, applied_at, result)
        VALUES (?, ?, ?, ?, ?, datetime('now'), ?)
        ON CONFLICT(op_id) DO UPDATE SET
            client_id=excluded.client_id,
            op_type=excluded.op_type,
            record_uuid=excluded.record_uuid,
            mutation_ts=excluded.mutation_ts,
            applied_at=datetime('now'),
            result=excluded.result
        """,
        (
            str(op_id or "").strip(),
            str(client_id or "").strip(),
            str(op_type or "").strip(),
            str(record_uuid or "").strip(),
            str(mutation_ts or "").strip(),
            str(result or ""),
        ),
    )
    if commit:
        conn.commit()


def get_applied_operation(conn: sqlite3.Connection, op_id: str) -> Optional[dict[str, Any]]:
    """Return the shared replay ledger row for the given operation, if present."""
    _ensure_applied_ops_table(conn)
    row = conn.execute(
        """
        SELECT op_id, client_id, op_type, record_uuid, mutation_ts, applied_at, result
        FROM applied_ops
        WHERE op_id=?
        """,
        (str(op_id or "").strip(),),
    ).fetchone()
    return dict(row) if row is not None else None


def record_applied_op(
    conn: sqlite3.Connection,
    op_id: str,
    *,
    client_id: str = "",
    op_type: str = "",
    record_uuid: str = "",
    mutation_ts: str = "",
    result: str = "",
    commit: bool = True,
) -> Optional[dict[str, Any]]:
    """Persist an applied operation and return the stored ledger row."""
    record_applied_operation(
        conn,
        op_id,
        client_id,
        op_type,
        record_uuid,
        mutation_ts,
        result=result,
        commit=commit,
    )
    return get_applied_operation(conn, op_id)


def get_applied_op(conn: sqlite3.Connection, op_id: str) -> Optional[dict[str, Any]]:
    """Getter-style alias for reading a replay ledger row."""
    return get_applied_operation(conn, op_id)


def has_applied_op(conn: sqlite3.Connection, op_id: str) -> bool:
    """Return whether an operation was already recorded as applied."""
    return get_applied_operation(conn, op_id) is not None


def list_applied_ops(conn: sqlite3.Connection, limit: Optional[int] = None) -> list[dict[str, Any]]:
    """List recently applied operations from the replay ledger."""
    _ensure_applied_ops_table(conn)
    sql = """
        SELECT op_id, client_id, op_type, record_uuid, mutation_ts, applied_at, result
        FROM applied_ops
        ORDER BY applied_at DESC, op_id DESC
    """
    params: tuple[Any, ...] = ()
    if limit is not None:
        sql += " LIMIT ?"
        params = (max(int(limit), 0),)
    rows = conn.execute(sql, params).fetchall()
    return [dict(row) for row in rows]


def delete_applied_op(conn: sqlite3.Connection, op_id: str, commit: bool = True) -> bool:
    """Delete a replay ledger row by operation id."""
    _ensure_applied_ops_table(conn)
    cur = conn.execute("DELETE FROM applied_ops WHERE op_id=?", (str(op_id or "").strip(),))
    if commit:
        conn.commit()
    return cur.rowcount > 0


def get_tombstone(conn: sqlite3.Connection, record_uuid: str) -> Optional[dict[str, Any]]:
    """Return the delete tombstone for a record UUID, if one exists."""
    _ensure_equipment_tombstones_table(conn)
    normalized_uuid = str(record_uuid or "").strip()
    if not normalized_uuid:
        return None
    row = conn.execute(
        """
        SELECT record_uuid, deleted_at, deleted_by_client_id, op_id
        FROM equipment_tombstones
        WHERE record_uuid=?
        """,
        (normalized_uuid,),
    ).fetchone()
    return dict(row) if row is not None else None


def upsert_tombstone(
    conn: sqlite3.Connection,
    record_uuid: str,
    deleted_at: str,
    deleted_by_client_id: str,
    op_id: str,
    commit: bool = True,
) -> None:
    """Insert or update a delete tombstone row."""
    _ensure_equipment_tombstones_table(conn)
    conn.execute(
        """
        INSERT INTO equipment_tombstones (record_uuid, deleted_at, deleted_by_client_id, op_id)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(record_uuid) DO UPDATE SET
            deleted_at=excluded.deleted_at,
            deleted_by_client_id=excluded.deleted_by_client_id,
            op_id=excluded.op_id
        """,
        (
            str(record_uuid or "").strip(),
            str(deleted_at or "").strip(),
            str(deleted_by_client_id or "").strip(),
            str(op_id or "").strip(),
        ),
    )
    if commit:
        conn.commit()


def clear_tombstone(conn: sqlite3.Connection, record_uuid: str, commit: bool = True) -> None:
    """Delete a tombstone row when a newer recreate wins."""
    _ensure_equipment_tombstones_table(conn)
    conn.execute("DELETE FROM equipment_tombstones WHERE record_uuid=?", (str(record_uuid or "").strip(),))
    if commit:
        conn.commit()


def get_equipment_tombstone(conn: sqlite3.Connection, record_uuid: str) -> Optional[dict[str, Any]]:
    """Getter-style alias for reading an equipment tombstone."""
    return get_tombstone(conn, record_uuid)


def upsert_equipment_tombstone(
    conn: sqlite3.Connection,
    record_uuid: str,
    *,
    deleted_at: str = "",
    deleted_by_client_id: str = "",
    op_id: str = "",
    commit: bool = True,
) -> Optional[dict[str, Any]]:
    """Insert or update an equipment tombstone and return the stored row."""
    normalized_uuid = str(record_uuid or "").strip()
    if not normalized_uuid:
        return None
    resolved_client_id = str(deleted_by_client_id or "").strip()
    if not resolved_client_id:
        resolved_client_id = ensure_client_identity(conn, commit=False)
    resolved_deleted_at = str(deleted_at or "").strip() or _current_timestamp()
    upsert_tombstone(
        conn,
        normalized_uuid,
        resolved_deleted_at,
        resolved_client_id,
        str(op_id or "").strip(),
        commit=commit,
    )
    return get_tombstone(conn, normalized_uuid)


def list_equipment_tombstones(
    conn: sqlite3.Connection,
    *,
    since: str = "",
    limit: Optional[int] = None,
) -> list[dict[str, Any]]:
    """List equipment tombstones in mutation order."""
    _ensure_equipment_tombstones_table(conn)
    sql = """
        SELECT record_uuid, deleted_at, deleted_by_client_id, op_id
        FROM equipment_tombstones
    """
    params: list[Any] = []
    if str(since or "").strip():
        sql += " WHERE deleted_at >= ?"
        params.append(str(since or "").strip())
    sql += " ORDER BY deleted_at, record_uuid"
    if limit is not None:
        sql += " LIMIT ?"
        params.append(max(int(limit), 0))
    rows = conn.execute(sql, tuple(params)).fetchall()
    return [dict(row) for row in rows]


def delete_equipment_tombstone(conn: sqlite3.Connection, record_uuid: str, commit: bool = True) -> bool:
    """Delete a tombstone row by record UUID."""
    _ensure_equipment_tombstones_table(conn)
    cur = conn.execute("DELETE FROM equipment_tombstones WHERE record_uuid=?", (str(record_uuid or "").strip(),))
    if commit:
        conn.commit()
    return cur.rowcount > 0


def fetch_equipment_tombstone_snapshot(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """Return a stable, ordered tombstone snapshot for sync transport."""
    _ensure_equipment_tombstones_table(conn)
    rows = conn.execute(
        f"SELECT {', '.join(_EQUIPMENT_TOMBSTONE_COPY_COLUMNS)} "
        "FROM equipment_tombstones ORDER BY deleted_at, record_uuid"
    ).fetchall()
    return [_row_to_snapshot_dict(row, _EQUIPMENT_TOMBSTONE_COPY_COLUMNS) for row in rows]


def fetch_equipment_snapshot(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """Return a stable, ordered equipment-table snapshot for sync transport."""
    rows = conn.execute(
        f"SELECT {', '.join(_EQUIPMENT_COPY_COLUMNS)} FROM equipment ORDER BY record_id"
    ).fetchall()
    return [_row_to_snapshot_dict(row, _EQUIPMENT_COPY_COLUMNS) for row in rows]


def fetch_import_issue_snapshot(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """Return a stable, ordered import-issues snapshot for sync transport."""
    rows = conn.execute(
        f"SELECT {', '.join(_IMPORT_ISSUE_COPY_COLUMNS)} FROM import_issues ORDER BY id"
    ).fetchall()
    return [_row_to_snapshot_dict(row, _IMPORT_ISSUE_COPY_COLUMNS) for row in rows]


def fetch_raw_cell_snapshot(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """Return a stable, ordered raw-cells snapshot for sync transport."""
    rows = conn.execute(
        f"SELECT {', '.join(_RAW_CELL_COPY_COLUMNS)} FROM raw_cells ORDER BY id"
    ).fetchall()
    return [_row_to_snapshot_dict(row, _RAW_CELL_COPY_COLUMNS) for row in rows]


def replace_local_snapshot(
    conn: Optional[sqlite3.Connection] = None,
    equipment_snapshot: Optional[Iterable[Mapping[str, Any]]] = None,
    import_issue_snapshot: Optional[Iterable[Mapping[str, Any]]] = None,
    raw_cell_snapshot: Optional[Iterable[Mapping[str, Any]]] = None,
    revision: Optional[str] = None,
    equipment_snapshot_hash: Optional[str] = None,
    import_issue_snapshot_hash: Optional[str] = None,
    global_mutation_at: Optional[str] = None,
    updated_at: Optional[str] = None,
    commit: bool = True,
    *,
    tombstone_snapshot: Optional[Iterable[Mapping[str, Any]]] = None,
    clear_outbox: bool = False,
    clear_applied_ops: bool = False,
    local_db_path: Optional[Path] = None,
    shared_db_path: Optional[Path] = None,
    local_path: Optional[Path] = None,
    shared_path: Optional[Path] = None,
    target_db_path: Optional[Path] = None,
    source_db_path: Optional[Path] = None,
) -> dict[str, int]:
    """Replace snapshot-backed tables from row payloads or from another database path."""
    resolved_target_path = local_db_path or local_path or target_db_path
    resolved_source_path = shared_db_path or shared_path or source_db_path

    if resolved_target_path is not None or resolved_source_path is not None:
        if resolved_target_path is None or resolved_source_path is None:
            raise ValueError("Both source and target database paths are required for path-based replacement.")
        if not commit:
            raise ValueError("Path-based snapshot replacement always commits; use a live connection for staged changes.")
        return replace_database_snapshot(
            resolved_target_path,
            resolved_source_path,
            clear_outbox=clear_outbox,
            clear_applied_ops=clear_applied_ops,
        )

    if not isinstance(conn, sqlite3.Connection):
        if _is_pathlike(conn) and _is_pathlike(equipment_snapshot) and import_issue_snapshot is None:
            if not commit:
                raise ValueError("Path-based snapshot replacement always commits; use a live connection for staged changes.")
            return replace_database_snapshot(conn, equipment_snapshot)
        raise TypeError("replace_local_snapshot requires either a sqlite connection or source/target database paths.")

    if equipment_snapshot is None or import_issue_snapshot is None:
        raise TypeError("Connection-based snapshot replacement requires equipment and import-issue snapshots.")

    _ensure_equipment_tombstones_table(conn)
    if clear_outbox:
        _ensure_sync_outbox_table(conn)
    if clear_applied_ops:
        _ensure_applied_ops_table(conn)

    equipment_rows = _prepare_snapshot_rows(
        equipment_snapshot,
        _EQUIPMENT_COPY_COLUMNS,
        optional_defaults=_OPTIONAL_SNAPSHOT_COLUMN_DEFAULTS.get("equipment"),
    )
    issue_rows = _prepare_snapshot_rows(import_issue_snapshot, _IMPORT_ISSUE_COPY_COLUMNS)
    raw_rows = None
    tombstone_rows = None
    if raw_cell_snapshot is not None:
        raw_rows = _prepare_snapshot_rows(raw_cell_snapshot, _RAW_CELL_COPY_COLUMNS)
    if tombstone_snapshot is not None:
        tombstone_rows = _prepare_snapshot_rows(
            tombstone_snapshot,
            _EQUIPMENT_TOMBSTONE_COPY_COLUMNS,
            optional_defaults=_OPTIONAL_SNAPSHOT_COLUMN_DEFAULTS.get("equipment_tombstones"),
        )
    began_transaction = False

    try:
        if not conn.in_transaction:
            conn.execute("BEGIN")
            began_transaction = True
        conn.execute("DELETE FROM equipment")
        conn.execute("DELETE FROM equipment_search")
        conn.execute("DELETE FROM import_issues")
        if raw_rows is not None:
            conn.execute("DELETE FROM raw_cells")
        if tombstone_rows is not None:
            conn.execute("DELETE FROM equipment_tombstones")
        if clear_outbox:
            conn.execute("DELETE FROM sync_outbox")
        if clear_applied_ops:
            conn.execute("DELETE FROM applied_ops")

        if equipment_rows:
            placeholders = ", ".join("?" for _ in _EQUIPMENT_COPY_COLUMNS)
            conn.executemany(
                f"""
                INSERT INTO equipment ({", ".join(_EQUIPMENT_COPY_COLUMNS)})
                VALUES ({placeholders})
                """,
                equipment_rows,
            )

        if issue_rows:
            placeholders = ", ".join("?" for _ in _IMPORT_ISSUE_COPY_COLUMNS)
            conn.executemany(
                f"""
                INSERT INTO import_issues ({", ".join(_IMPORT_ISSUE_COPY_COLUMNS)})
                VALUES ({placeholders})
                """,
                issue_rows,
            )

        if raw_rows:
            placeholders = ", ".join("?" for _ in _RAW_CELL_COPY_COLUMNS)
            conn.executemany(
                f"""
                INSERT INTO raw_cells ({", ".join(_RAW_CELL_COPY_COLUMNS)})
                VALUES ({placeholders})
                """,
                raw_rows,
            )

        if tombstone_rows:
            placeholders = ", ".join("?" for _ in _EQUIPMENT_TOMBSTONE_COPY_COLUMNS)
            conn.executemany(
                f"""
                INSERT INTO equipment_tombstones ({", ".join(_EQUIPMENT_TOMBSTONE_COPY_COLUMNS)})
                VALUES ({placeholders})
                """,
                tombstone_rows,
            )

        _ensure_equipment_record_uuids(conn)
        _ensure_equipment_search_index(conn)
        set_sync_state(
            conn,
            revision=_SYNC_STATE_DEFAULTS["revision"] if revision is None else revision,
            equipment_snapshot_hash=(
                _SYNC_STATE_DEFAULTS["equipment_snapshot_hash"]
                if equipment_snapshot_hash is None
                else equipment_snapshot_hash
            ),
            import_issue_snapshot_hash=(
                _SYNC_STATE_DEFAULTS["import_issue_snapshot_hash"]
                if import_issue_snapshot_hash is None
                else import_issue_snapshot_hash
            ),
            global_mutation_at=(
                _SYNC_STATE_DEFAULTS["global_mutation_at"]
                if global_mutation_at is None
                else global_mutation_at
            ),
            updated_at=updated_at,
            commit=False,
        )

        stats = {
            "equipment_records": conn.execute("SELECT COUNT(*) FROM equipment").fetchone()[0],
            "raw_cells": conn.execute("SELECT COUNT(*) FROM raw_cells").fetchone()[0],
            "import_issues": conn.execute("SELECT COUNT(*) FROM import_issues").fetchone()[0],
            "equipment_tombstones": conn.execute("SELECT COUNT(*) FROM equipment_tombstones").fetchone()[0],
        }
        if commit:
            conn.commit()
        return stats
    except Exception:
        if began_transaction and conn.in_transaction:
            conn.rollback()
        raise


def replace_database_snapshot(
    target_db_path: Any,
    source_db_path: Any,
    *,
    clear_outbox: bool = False,
    clear_applied_ops: bool = False,
) -> dict[str, int]:
    """Copy snapshot-backed tables from one database file into another safely."""
    source_path = _coerce_path(source_db_path)
    target_path = _coerce_path(target_db_path)
    if not source_path.exists():
        raise FileNotFoundError(f"Database file not found: {source_path}")

    source_path = source_path.resolve()
    target_path = target_path.resolve()
    if source_path == target_path:
        conn = get_connection(target_path)
        try:
            create_tables(conn)
            return _snapshot_counts(conn)
        finally:
            conn.close()

    target_path.parent.mkdir(parents=True, exist_ok=True)
    source_conn = get_connection(source_path)
    target_conn = get_connection(target_path)
    try:
        create_tables(source_conn)
        create_tables(target_conn)
        source_state = load_sync_state(source_conn)
        stats = replace_local_snapshot(
            target_conn,
            fetch_equipment_snapshot(source_conn),
            fetch_import_issue_snapshot(source_conn),
            raw_cell_snapshot=fetch_raw_cell_snapshot(source_conn),
            tombstone_snapshot=fetch_equipment_tombstone_snapshot(source_conn),
            revision=source_state["revision"],
            equipment_snapshot_hash=source_state["equipment_snapshot_hash"],
            import_issue_snapshot_hash=source_state["import_issue_snapshot_hash"],
            global_mutation_at=source_state["global_mutation_at"],
            updated_at=source_state["updated_at"],
            clear_outbox=clear_outbox,
            clear_applied_ops=clear_applied_ops,
            commit=True,
        )
        return stats
    finally:
        source_conn.close()
        target_conn.close()


def copy_database_snapshot(
    target_db_path: Any,
    source_db_path: Any,
    *,
    clear_outbox: bool = False,
    clear_applied_ops: bool = False,
) -> dict[str, int]:
    """Alias for replacing one database snapshot from another database file."""
    return replace_database_snapshot(
        target_db_path,
        source_db_path,
        clear_outbox=clear_outbox,
        clear_applied_ops=clear_applied_ops,
    )


def import_database_snapshot(conn: sqlite3.Connection, source_db_path: Path) -> dict[str, int]:
    """Replace the current database contents with data from another compatible DB snapshot."""
    source_path = Path(source_db_path).expanduser()
    if not source_path.exists():
        raise FileNotFoundError(f"Database file not found: {source_path}")
    source_path = source_path.resolve()

    target_path = get_database_path(conn)
    if target_path is not None and target_path.resolve() == source_path:
        raise ValueError("Choose a different database file than the one currently open in the app.")

    create_tables(conn)

    try:
        conn.execute("ATTACH DATABASE ? AS import_source", (str(source_path),))
        _validate_import_source_schema(conn)

        source_has_raw_cells = _attached_table_exists(conn, "import_source", "raw_cells")
        source_has_import_issues = _attached_table_exists(conn, "import_source", "import_issues")

        conn.execute("BEGIN")
        clear_all_data(conn, commit=False)
        _copy_attached_table(conn, "equipment", _EQUIPMENT_COPY_COLUMNS)
        _copy_attached_table(conn, "raw_cells", _RAW_CELL_COPY_COLUMNS, required=source_has_raw_cells)
        _copy_attached_table(conn, "import_issues", _IMPORT_ISSUE_COPY_COLUMNS, required=source_has_import_issues)
        _ensure_equipment_record_uuids(conn)
        _ensure_equipment_search_index(conn)

        stats = {
            "equipment_records": conn.execute("SELECT COUNT(*) FROM equipment").fetchone()[0],
            "raw_cells": conn.execute("SELECT COUNT(*) FROM raw_cells").fetchone()[0],
            "import_issues": conn.execute("SELECT COUNT(*) FROM import_issues").fetchone()[0],
        }
        conn.commit()
        return stats
    except Exception:
        if conn.in_transaction:
            conn.rollback()
        raise
    finally:
        try:
            conn.execute("DETACH DATABASE import_source")
        except sqlite3.Error:
            pass


# ── Equipment CRUD ──────────────────────────────────────────────────────────

def insert_equipment(
    conn: sqlite3.Connection,
    eq: Equipment,
    commit: bool = True,
) -> int:
    """Insert an equipment record and return the new record_id."""
    created_at = eq.created_at or _current_timestamp()
    updated_at = eq.updated_at or created_at
    cur = conn.execute("""
        INSERT INTO equipment (
            record_uuid, asset_number, serial_number, manufacturer, manufacturer_raw,
            model, description, qty,
            location, assigned_to, ownership_type, rental_vendor, rental_cost_monthly,
            calibration_status, last_calibration_date, calibration_due_date,
            calibration_vendor, calibration_cost,
            lifecycle_status, working_status, condition,
            acquired_date, estimated_age_years, age_basis,
            verified_in_survey, blue_dot_ref,
            project_name, picture_path, links, notes, manual_entry, is_archived, source_refs,
            created_at, updated_at
        ) VALUES (
            ?, ?, ?, ?, ?,
            ?, ?, ?,
            ?, ?, ?, ?, ?,
            ?, ?, ?,
            ?, ?,
            ?, ?, ?,
            ?, ?, ?, ?,
            ?, ?, ?,
            ?, ?, ?, ?, ?, ?, ?
        )
    """, (
        _ensure_record_uuid(eq), eq.asset_number, eq.serial_number, eq.manufacturer, eq.manufacturer_raw,
        eq.model, eq.description, eq.qty,
        eq.location, eq.assigned_to, eq.ownership_type, eq.rental_vendor, eq.rental_cost_monthly,
        eq.calibration_status, eq.last_calibration_date, eq.calibration_due_date,
        eq.calibration_vendor, eq.calibration_cost,
        eq.lifecycle_status, eq.working_status, eq.condition,
        eq.acquired_date, eq.estimated_age_years, eq.age_basis,
        1 if eq.verified_in_survey else 0, eq.blue_dot_ref,
        eq.project_name,
        eq.picture_path,
        eq.links,
        eq.notes,
        1 if eq.manual_entry else 0,
        1 if eq.is_archived else 0,
        eq.source_refs,
        created_at,
        updated_at,
    ))
    record_id = cur.lastrowid
    eq.created_at = created_at
    eq.updated_at = updated_at
    _upsert_equipment_search_row(conn, record_id, eq)
    if commit:
        conn.commit()
    return record_id


def update_equipment(conn: sqlite3.Connection, eq: Equipment, commit: bool = True) -> None:
    """Update an existing equipment record by record_id."""
    updated_at = eq.updated_at or _current_timestamp()
    conn.execute("""
        UPDATE equipment SET
            record_uuid=?, asset_number=?, serial_number=?, manufacturer=?, manufacturer_raw=?,
            model=?, description=?, qty=?,
            location=?, assigned_to=?, ownership_type=?, rental_vendor=?, rental_cost_monthly=?,
            calibration_status=?, last_calibration_date=?, calibration_due_date=?,
            calibration_vendor=?, calibration_cost=?,
            lifecycle_status=?, working_status=?, condition=?,
            acquired_date=?, estimated_age_years=?, age_basis=?,
            verified_in_survey=?, blue_dot_ref=?,
            project_name=?, picture_path=?, links=?, notes=?, manual_entry=?, is_archived=?, source_refs=?,
            updated_at=?
        WHERE record_id=?
    """, (
        _ensure_record_uuid(eq), eq.asset_number, eq.serial_number, eq.manufacturer, eq.manufacturer_raw,
        eq.model, eq.description, eq.qty,
        eq.location, eq.assigned_to, eq.ownership_type, eq.rental_vendor, eq.rental_cost_monthly,
        eq.calibration_status, eq.last_calibration_date, eq.calibration_due_date,
        eq.calibration_vendor, eq.calibration_cost,
        eq.lifecycle_status, eq.working_status, eq.condition,
        eq.acquired_date, eq.estimated_age_years, eq.age_basis,
        1 if eq.verified_in_survey else 0, eq.blue_dot_ref,
        eq.project_name,
        eq.picture_path,
        eq.links,
        eq.notes,
        1 if eq.manual_entry else 0,
        1 if eq.is_archived else 0,
        eq.source_refs,
        updated_at,
        eq.record_id,
    ))
    eq.updated_at = updated_at
    _upsert_equipment_search_row(conn, eq.record_id, eq)
    if commit:
        conn.commit()


def delete_equipment(conn: sqlite3.Connection, record_id: int, commit: bool = True) -> None:
    """Delete an equipment record by record_id."""
    conn.execute("DELETE FROM equipment WHERE record_id=?", (record_id,))
    conn.execute("DELETE FROM equipment_search WHERE record_id=?", (record_id,))
    if commit:
        conn.commit()


def get_equipment_by_id(conn: sqlite3.Connection, record_id: int) -> Optional[Equipment]:
    """Fetch a single equipment record by record_id."""
    row = conn.execute("SELECT * FROM equipment WHERE record_id=?", (record_id,)).fetchone()
    if row is None:
        return None
    return _row_to_equipment(row)


def get_equipment_by_uuid(conn: sqlite3.Connection, record_uuid: str) -> Optional[Equipment]:
    """Fetch a single equipment record by record_uuid."""
    normalized_uuid = (record_uuid or "").strip()
    if not normalized_uuid:
        return None
    row = conn.execute("SELECT * FROM equipment WHERE record_uuid=?", (normalized_uuid,)).fetchone()
    if row is None:
        return None
    return _row_to_equipment(row)


def get_all_equipment(conn: sqlite3.Connection, archived: str = "all") -> list[Equipment]:
    """Fetch all equipment records."""
    where_sql, params = _archive_where_clause(archived)
    sql = "SELECT * FROM equipment"
    if where_sql:
        sql += f" WHERE {where_sql}"
    sql += " ORDER BY asset_number"
    rows = conn.execute(sql, params).fetchall()
    return [_row_to_equipment(r) for r in rows]


def get_distinct_equipment_values(
    conn: sqlite3.Connection,
    field: str,
    limit: int = 200,
) -> list[str]:
    """Fetch distinct non-empty values for a whitelisted equipment field."""
    allowed_fields = {
        "asset_number",
        "serial_number",
        "manufacturer",
        "model",
        "description",
        "project_name",
        "location",
        "assigned_to",
        "calibration_vendor",
        "lifecycle_status",
        "working_status",
        "calibration_status",
    }
    if field not in allowed_fields:
        raise ValueError(f"Unsupported equipment field: {field}")

    rows = conn.execute(
        f"""
        SELECT DISTINCT {field}
        FROM equipment
        WHERE TRIM(COALESCE({field}, '')) <> ''
        ORDER BY {field} COLLATE NOCASE
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    return [row[0] for row in rows if row[0]]


def search_equipment(
    conn: sqlite3.Connection,
    query: str,
    lifecycle: str = "",
    calibration: str = "",
    working: str = "",
    location: str = "",
    asset_number: str = "",
    manufacturer: str = "",
    model: str = "",
    description: str = "",
    estimated_age_years: str = "",
    archived: str = "active",
) -> list[Equipment]:
    """Search equipment with multi-word Google-style query.

    Each word in the query must match somewhere in the record (AND logic).
    For example, "fluke multimeter" finds records containing both words
    across any combination of fields.
    """
    query = query.strip()
    filters = {
        "asset_number": asset_number,
        "manufacturer": manufacturer,
        "model": model,
        "description": description,
        "estimated_age_years": estimated_age_years,
        "lifecycle": lifecycle,
        "calibration": calibration,
        "working": working,
        "location": location,
    }

    if query and _can_use_fts(query):
        try:
            rows = _search_equipment_with_fts(conn, query, filters, archived=archived)
            if rows:
                return [_row_to_equipment(r) for r in rows]
        except sqlite3.OperationalError:
            pass

    rows = _search_equipment_with_like(conn, query, filters, archived=archived)
    return [_row_to_equipment(r) for r in rows]


def get_equipment_stats(conn: sqlite3.Connection, archived: str = "all") -> dict:
    """Get summary statistics about equipment."""
    where_sql, params = _archive_where_clause(archived)
    where_clause = f"WHERE {where_sql}" if where_sql else ""
    row = conn.execute(
        f"""
        SELECT
            COUNT(*) AS total,
            SUM(CASE WHEN lifecycle_status='active' THEN 1 ELSE 0 END) AS active,
            SUM(CASE WHEN lifecycle_status='repair' THEN 1 ELSE 0 END) AS repair,
            SUM(CASE WHEN lifecycle_status='scrapped' THEN 1 ELSE 0 END) AS scrapped,
            SUM(CASE WHEN lifecycle_status='missing' THEN 1 ELSE 0 END) AS missing,
            SUM(CASE WHEN calibration_status='calibrated' THEN 1 ELSE 0 END) AS calibrated,
            SUM(CASE WHEN calibration_status='reference_only' THEN 1 ELSE 0 END) AS reference_only,
            SUM(CASE WHEN verified_in_survey=1 THEN 1 ELSE 0 END) AS verified_in_survey,
            SUM(CASE WHEN COALESCE(is_archived, 0)=1 THEN 1 ELSE 0 END) AS archived
        FROM equipment
        {where_clause}
        """,
        params,
    ).fetchone()
    import_issues = conn.execute(
        "SELECT COUNT(*) FROM import_issues WHERE resolution_status='unresolved'"
    ).fetchone()[0]
    return {
        "total": row["total"] or 0,
        "active": row["active"] or 0,
        "repair": row["repair"] or 0,
        "scrapped": row["scrapped"] or 0,
        "missing": row["missing"] or 0,
        "calibrated": row["calibrated"] or 0,
        "reference_only": row["reference_only"] or 0,
        "verified_in_survey": row["verified_in_survey"] or 0,
        "archived": row["archived"] or 0,
        "import_issues": import_issues,
    }


# ── Raw Cells ───────────────────────────────────────────────────────────────

def insert_raw_cells_batch(
    conn: sqlite3.Connection,
    cells: list[RawCell],
    commit: bool = True,
) -> None:
    """Bulk insert raw cells for search indexing."""
    conn.executemany("""
        INSERT INTO raw_cells (source_file, source_sheet, row_number, column_number,
                               cell_address, cell_value, row_preview)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, [
        (c.source_file, c.source_sheet, c.row_number, c.column_number,
         c.cell_address, c.cell_value, c.row_preview)
        for c in cells
    ])
    if commit:
        conn.commit()


def search_raw_cells(conn: sqlite3.Connection, query: str,
                     limit: int = 500) -> list[RawCell]:
    """Search raw cells by value substring."""
    rows = conn.execute("""
        SELECT * FROM raw_cells
        WHERE cell_value LIKE ?
        ORDER BY source_file, source_sheet, row_number, column_number
        LIMIT ?
    """, (f"%{query}%", limit)).fetchall()
    return [_row_to_raw_cell(r) for r in rows]


# ── Import Issues ───────────────────────────────────────────────────────────

def insert_import_issue(
    conn: sqlite3.Connection,
    issue: ImportIssue,
    commit: bool = True,
) -> int:
    """Insert an import issue and return the new id."""
    cur = conn.execute("""
        INSERT INTO import_issues (issue_type, source_file, source_sheet, source_row,
                                   asset_number, serial_number, summary, raw_data,
                                   resolution_status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        issue.issue_type, issue.source_file, issue.source_sheet, issue.source_row,
        issue.asset_number, issue.serial_number, issue.summary, issue.raw_data,
        issue.resolution_status,
    ))
    if commit:
        conn.commit()
    return cur.lastrowid


def get_all_import_issues(conn: sqlite3.Connection,
                          status: str = "") -> list[ImportIssue]:
    """Fetch import issues, optionally filtered by resolution status."""
    if status:
        rows = conn.execute(
            "SELECT * FROM import_issues WHERE resolution_status=? ORDER BY id",
            (status,)
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM import_issues ORDER BY id").fetchall()
    return [_row_to_import_issue(r) for r in rows]


def update_issue_status(conn: sqlite3.Connection, issue_id: int,
                        new_status: str) -> None:
    """Update the resolution status of an import issue."""
    conn.execute(
        "UPDATE import_issues SET resolution_status=? WHERE id=?",
        (new_status, issue_id)
    )
    conn.commit()


def clear_all_data(conn: sqlite3.Connection, commit: bool = True) -> None:
    """Delete all data from all tables (for re-import)."""
    conn.execute("DELETE FROM equipment")
    conn.execute("DELETE FROM equipment_search")
    conn.execute("DELETE FROM raw_cells")
    conn.execute("DELETE FROM import_issues")
    if commit:
        conn.commit()


# ── Helpers ─────────────────────────────────────────────────────────────────

def _row_to_equipment(row: sqlite3.Row) -> Equipment:
    return Equipment(
        record_id=row["record_id"],
        record_uuid=row["record_uuid"] if "record_uuid" in row.keys() else "",
        asset_number=row["asset_number"] or "",
        serial_number=row["serial_number"] or "",
        manufacturer=row["manufacturer"] or "",
        manufacturer_raw=row["manufacturer_raw"] or "",
        model=row["model"] or "",
        description=row["description"] or "",
        qty=row["qty"],
        location=row["location"] or "",
        assigned_to=row["assigned_to"] or "",
        ownership_type=row["ownership_type"] or "owned",
        rental_vendor=row["rental_vendor"] or "",
        rental_cost_monthly=row["rental_cost_monthly"],
        calibration_status=row["calibration_status"] or "unknown",
        last_calibration_date=row["last_calibration_date"] or "",
        calibration_due_date=row["calibration_due_date"] or "",
        calibration_vendor=row["calibration_vendor"] or "",
        calibration_cost=row["calibration_cost"],
        lifecycle_status=row["lifecycle_status"] or "active",
        working_status=row["working_status"] or "unknown",
        condition=row["condition"] or "",
        acquired_date=row["acquired_date"] or "",
        estimated_age_years=row["estimated_age_years"],
        age_basis=row["age_basis"] or "unknown",
        verified_in_survey=bool(row["verified_in_survey"]),
        blue_dot_ref=row["blue_dot_ref"] or "",
        project_name=row["project_name"] or "",
        picture_path=row["picture_path"] or "",
        links=row["links"] or "",
        notes=row["notes"] or "",
        manual_entry=bool(row["manual_entry"]),
        is_archived=bool(row["is_archived"]) if "is_archived" in row.keys() else False,
        source_refs=row["source_refs"] or "[]",
        created_at=row["created_at"] or "",
        updated_at=row["updated_at"] or "",
    )


def _row_to_raw_cell(row: sqlite3.Row) -> RawCell:
    return RawCell(
        id=row["id"],
        source_file=row["source_file"] or "",
        source_sheet=row["source_sheet"] or "",
        row_number=row["row_number"],
        column_number=row["column_number"],
        cell_address=row["cell_address"] or "",
        cell_value=row["cell_value"] or "",
        row_preview=row["row_preview"] or "",
    )


def _row_to_import_issue(row: sqlite3.Row) -> ImportIssue:
    return ImportIssue(
        id=row["id"],
        issue_type=row["issue_type"] or "",
        source_file=row["source_file"] or "",
        source_sheet=row["source_sheet"] or "",
        source_row=row["source_row"],
        asset_number=row["asset_number"] or "",
        serial_number=row["serial_number"] or "",
        summary=row["summary"] or "",
        raw_data=row["raw_data"] or "{}",
        resolution_status=row["resolution_status"] or "unresolved",
        created_at=row["created_at"] or "",
    )


def _search_equipment_with_like(
    conn: sqlite3.Connection,
    query: str,
    filters: dict[str, str],
    archived: str,
) -> list[sqlite3.Row]:
    """Run the legacy LIKE-based search path."""
    search_fields = """(
        asset_number LIKE ? OR serial_number LIKE ? OR
        manufacturer LIKE ? OR manufacturer_raw LIKE ? OR
        model LIKE ? OR description LIKE ? OR project_name LIKE ? OR location LIKE ? OR
        assigned_to LIKE ? OR notes LIKE ? OR condition LIKE ? OR
        calibration_status LIKE ? OR lifecycle_status LIKE ? OR
        working_status LIKE ? OR calibration_vendor LIKE ? OR
        rental_vendor LIKE ?
    )"""
    field_count = 16
    conditions = []
    params: list = []

    if query:
        for word in query.split():
            conditions.append(search_fields)
            params.extend([f"%{word}%"] * field_count)

    _append_archive_filter(conditions, params, archived)
    _append_exact_filters(conditions, params, filters)

    where = " AND ".join(conditions) if conditions else "1=1"
    sql = f"SELECT * FROM equipment WHERE {where} ORDER BY asset_number"
    return conn.execute(sql, params).fetchall()


def _search_equipment_with_fts(
    conn: sqlite3.Connection,
    query: str,
    filters: dict[str, str],
    archived: str,
) -> list[sqlite3.Row]:
    """Run the FTS-backed search path, preserving the existing filters."""
    conditions = ["s.search_text MATCH ?"]
    params: list = [query]
    _append_archive_filter(conditions, params, archived, equipment_alias="e")
    _append_exact_filters(conditions, params, filters, equipment_alias="e")

    where = " AND ".join(conditions)
    sql = f"""
        SELECT e.*
        FROM equipment_search AS s
        JOIN equipment AS e ON e.record_id = s.record_id
        WHERE {where}
        ORDER BY bm25(s), e.asset_number
    """
    return conn.execute(sql, params).fetchall()


def _append_exact_filters(
    conditions: list[str],
    params: list,
    filters: dict[str, str],
    equipment_alias: str = "",
) -> None:
    """Append the shared non-FTS filters to a search query."""
    prefix = f"{equipment_alias}." if equipment_alias else ""

    if filters["asset_number"]:
        conditions.append(f"{prefix}asset_number LIKE ?")
        params.append(f"%{filters['asset_number']}%")

    if filters["manufacturer"]:
        conditions.append(f"({prefix}manufacturer LIKE ? OR {prefix}manufacturer_raw LIKE ?)")
        params.extend([f"%{filters['manufacturer']}%", f"%{filters['manufacturer']}%"])

    if filters["model"]:
        conditions.append(f"{prefix}model LIKE ?")
        params.append(f"%{filters['model']}%")

    if filters["description"]:
        conditions.append(f"{prefix}description LIKE ?")
        params.append(f"%{filters['description']}%")

    if filters["estimated_age_years"]:
        conditions.append(f"CAST(COALESCE({prefix}estimated_age_years, '') AS TEXT) LIKE ?")
        params.append(f"%{filters['estimated_age_years']}%")

    if filters["lifecycle"]:
        conditions.append(f"{prefix}lifecycle_status = ?")
        params.append(filters["lifecycle"])

    if filters["calibration"]:
        conditions.append(f"{prefix}calibration_status = ?")
        params.append(filters["calibration"])

    if filters["working"]:
        conditions.append(f"{prefix}working_status = ?")
        params.append(filters["working"])

    if filters["location"]:
        conditions.append(f"{prefix}location LIKE ?")
        params.append(f"%{filters['location']}%")


def _append_archive_filter(
    conditions: list[str],
    params: list,
    archived: str,
    equipment_alias: str = "",
) -> None:
    """Append the shared archive-state filter to a query when needed."""
    where_sql, where_params = _archive_where_clause(archived, equipment_alias=equipment_alias)
    if not where_sql:
        return
    conditions.append(where_sql)
    params.extend(where_params)


def _archive_where_clause(archived: str, equipment_alias: str = "") -> tuple[str, list[int]]:
    """Return the SQL fragment and params for the requested archive scope."""
    prefix = f"{equipment_alias}." if equipment_alias else ""
    normalized = (archived or "all").strip().lower()

    if normalized == "all":
        return "", []
    if normalized == "active":
        return f"COALESCE({prefix}is_archived, 0)=0", []
    if normalized == "archived":
        return f"COALESCE({prefix}is_archived, 0)=1", []

    raise ValueError(f"Unsupported archive scope: {archived}")


def _upsert_equipment_search_row(conn: sqlite3.Connection, record_id: int | None, eq: Equipment) -> None:
    """Insert or replace a row in the FTS index."""
    if record_id is None:
        return

    conn.execute("DELETE FROM equipment_search WHERE record_id=?", (record_id,))
    conn.execute(
        "INSERT INTO equipment_search (record_id, search_text) VALUES (?, ?)",
        (record_id, _build_equipment_search_text(eq)),
    )


def _build_equipment_search_text(eq: Equipment) -> str:
    """Flatten searchable fields into a single FTS text blob."""
    parts = []
    for field in _SEARCH_TEXT_FIELDS:
        value = getattr(eq, field, "")
        if value is None:
            continue
        text = str(value).strip()
        if text:
            parts.append(text)
    return " ".join(parts)


def _ensure_equipment_search_index(conn: sqlite3.Connection) -> None:
    """Backfill or repair the FTS index for existing databases."""
    equipment_count = conn.execute("SELECT COUNT(*) FROM equipment").fetchone()[0]
    search_count = conn.execute("SELECT COUNT(*) FROM equipment_search").fetchone()[0]
    if equipment_count == search_count:
        return

    conn.execute("DELETE FROM equipment_search")
    rows = conn.execute("SELECT * FROM equipment").fetchall()
    for row in rows:
        eq = _row_to_equipment(row)
        _upsert_equipment_search_row(conn, eq.record_id, eq)


def _ensure_equipment_column(conn: sqlite3.Connection, column_name: str, definition: str) -> None:
    """Add a new equipment column to older databases when needed."""
    columns = _table_columns(conn, "equipment")
    if column_name in columns:
        return
    conn.execute(f"ALTER TABLE equipment ADD COLUMN {column_name} {definition}")


def _ensure_sync_state_column(conn: sqlite3.Connection, column_name: str, definition: str) -> None:
    """Add a missing sync_state column for older sync-state schemas."""
    columns = _table_columns(conn, "sync_state")
    if column_name in columns:
        return
    conn.execute(f"ALTER TABLE sync_state ADD COLUMN {column_name} {definition}")


def _ensure_sync_state_table(conn: sqlite3.Connection) -> None:
    """Ensure the singleton sync-state table exists and has the required columns."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS sync_state (
            id                         INTEGER PRIMARY KEY CHECK (id = 1),
            revision                   TEXT DEFAULT '',
            equipment_snapshot_hash    TEXT DEFAULT '',
            import_issue_snapshot_hash TEXT DEFAULT '',
            global_mutation_at         TEXT DEFAULT '',
            updated_at                 TEXT DEFAULT (datetime('now'))
        )
        """
    )
    _ensure_sync_state_column(conn, "revision", "TEXT DEFAULT ''")
    _ensure_sync_state_column(conn, "equipment_snapshot_hash", "TEXT DEFAULT ''")
    _ensure_sync_state_column(conn, "import_issue_snapshot_hash", "TEXT DEFAULT ''")
    _ensure_sync_state_column(conn, "global_mutation_at", "TEXT DEFAULT ''")
    _ensure_sync_state_column(conn, "updated_at", "TEXT DEFAULT (datetime('now'))")
    conn.execute("INSERT OR IGNORE INTO sync_state (id) VALUES (?)", (_SYNC_STATE_ROW_ID,))


def _ensure_client_identity_table(conn: sqlite3.Connection) -> None:
    """Ensure the singleton client-identity table exists."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS client_identity (
            id         INTEGER PRIMARY KEY CHECK (id = 1),
            client_id  TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now'))
        )
        """
    )
    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_client_identity_client_id ON client_identity(client_id)")
    conn.execute("INSERT OR IGNORE INTO client_identity (id) VALUES (?)", (_CLIENT_IDENTITY_ROW_ID,))


def _ensure_sync_outbox_table(conn: sqlite3.Connection) -> None:
    """Ensure the local outbox table exists."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS sync_outbox (
            op_id            TEXT PRIMARY KEY,
            client_id        TEXT DEFAULT '',
            op_type          TEXT DEFAULT '',
            record_uuid      TEXT DEFAULT '',
            mutation_ts      TEXT DEFAULT '',
            payload_json     TEXT DEFAULT '{}',
            artifact_path    TEXT DEFAULT '',
            status           TEXT DEFAULT 'pending',
            attempt_count    INTEGER DEFAULT 0,
            last_error       TEXT DEFAULT '',
            created_at       TEXT DEFAULT (datetime('now')),
            last_attempt_at  TEXT DEFAULT ''
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_sync_outbox_status_created ON sync_outbox(status, created_at)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_sync_outbox_record_uuid ON sync_outbox(record_uuid)")


def _ensure_applied_ops_table(conn: sqlite3.Connection) -> None:
    """Ensure the shared replay ledger exists."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS applied_ops (
            op_id       TEXT PRIMARY KEY,
            client_id   TEXT DEFAULT '',
            op_type     TEXT DEFAULT '',
            record_uuid TEXT DEFAULT '',
            mutation_ts TEXT DEFAULT '',
            applied_at  TEXT DEFAULT (datetime('now')),
            result      TEXT DEFAULT ''
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_applied_ops_applied_at ON applied_ops(applied_at)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_applied_ops_record_uuid ON applied_ops(record_uuid)")


def _ensure_equipment_tombstones_table(conn: sqlite3.Connection) -> None:
    """Ensure shared delete tombstones exist."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS equipment_tombstones (
            record_uuid           TEXT PRIMARY KEY,
            deleted_at            TEXT DEFAULT '',
            deleted_by_client_id  TEXT DEFAULT '',
            op_id                 TEXT DEFAULT ''
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_equipment_tombstones_deleted_at ON equipment_tombstones(deleted_at)")


def _ensure_equipment_record_uuids(conn: sqlite3.Connection) -> None:
    """Backfill stable UUIDs for equipment rows that do not have one yet."""
    rows = conn.execute(
        """
        SELECT record_id
        FROM equipment
        WHERE TRIM(COALESCE(record_uuid, '')) = ''
        """
    ).fetchall()
    for row in rows:
        record_id = row["record_id"] if isinstance(row, sqlite3.Row) else row[0]
        conn.execute(
            "UPDATE equipment SET record_uuid=? WHERE record_id=?",
            (_new_record_uuid(), record_id),
        )


def _ensure_record_uuid(eq: Equipment) -> str:
    """Return a stable record UUID for an equipment instance."""
    if not eq.record_uuid.strip():
        eq.record_uuid = _new_record_uuid()
    return eq.record_uuid


def _new_record_uuid() -> str:
    """Return a new stable record UUID string."""
    return uuid.uuid4().hex


def _current_timestamp() -> str:
    """Return a stable UTC timestamp string for mutation ordering."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _is_pathlike(value: Any) -> bool:
    """Return whether the provided value can be interpreted as a filesystem path."""
    return isinstance(value, (str, Path))


def _coerce_path(value: Any) -> Path:
    """Normalize a path-like value into a resolved pathlib Path."""
    if isinstance(value, Path):
        return value.expanduser()
    if isinstance(value, str) and value.strip():
        return Path(value).expanduser()
    raise TypeError("Expected a filesystem path.")


def _json_dumps(value: Any, default: str = "{}") -> str:
    """Serialize JSON payloads while preserving already-string values."""
    if value is _UNSET:
        return default
    if value is None:
        return default
    if isinstance(value, str):
        return value
    return json.dumps(value, sort_keys=True, default=str, separators=(",", ":"))


def _json_loads(value: str) -> Any:
    """Best-effort JSON parse used for queue payloads."""
    text = str(value or "")
    if not text:
        return {}
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def _normalize_outbox_row(row: Any) -> dict[str, Any]:
    """Return a queue row with a parsed payload helper field."""
    normalized = dict(row) if row is not None else {}
    if "payload_json" in normalized:
        normalized["payload"] = _json_loads(normalized["payload_json"])
    return normalized


def _snapshot_counts(conn: sqlite3.Connection) -> dict[str, int]:
    """Return counts for the snapshot-backed tables."""
    _ensure_equipment_tombstones_table(conn)
    return {
        "equipment_records": conn.execute("SELECT COUNT(*) FROM equipment").fetchone()[0],
        "raw_cells": conn.execute("SELECT COUNT(*) FROM raw_cells").fetchone()[0],
        "import_issues": conn.execute("SELECT COUNT(*) FROM import_issues").fetchone()[0],
        "equipment_tombstones": conn.execute("SELECT COUNT(*) FROM equipment_tombstones").fetchone()[0],
    }


def _table_columns(conn: sqlite3.Connection, table_name: str) -> set[str]:
    """Return the column names for a local table."""
    rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    result = set()
    for row in rows:
        if isinstance(row, sqlite3.Row):
            result.add(row["name"])
        else:
            result.add(row[1])
    return result


def _attached_table_exists(conn: sqlite3.Connection, database_name: str, table_name: str) -> bool:
    """Return whether an attached database contains the named table."""
    row = conn.execute(
        f"SELECT 1 FROM {database_name}.sqlite_master WHERE type='table' AND name=?",
        (table_name,),
    ).fetchone()
    return row is not None


def _attached_table_columns(conn: sqlite3.Connection, database_name: str, table_name: str) -> set[str]:
    """Return the column names for a table inside an attached database."""
    rows = conn.execute(f"PRAGMA {database_name}.table_info({table_name})").fetchall()
    return {row["name"] if hasattr(row, "keys") else row[1] for row in rows}


def _validate_import_source_schema(conn: sqlite3.Connection) -> None:
    """Ensure the attached database looks like a compatible app snapshot."""
    if not _attached_table_exists(conn, "import_source", "equipment"):
        raise ValueError(f"Selected file is not a {APP_CONFIG.database_label}.")

    _require_attached_columns(
        conn,
        "import_source",
        "equipment",
        _required_attached_columns("equipment", _EQUIPMENT_COPY_COLUMNS),
    )

    if _attached_table_exists(conn, "import_source", "raw_cells"):
        _require_attached_columns(conn, "import_source", "raw_cells", _RAW_CELL_COPY_COLUMNS)

    if _attached_table_exists(conn, "import_source", "import_issues"):
        _require_attached_columns(conn, "import_source", "import_issues", _IMPORT_ISSUE_COPY_COLUMNS)


def _require_attached_columns(
    conn: sqlite3.Connection,
    database_name: str,
    table_name: str,
    required_columns: tuple[str, ...],
) -> None:
    """Raise a friendly error when a selected database is missing expected columns."""
    available_columns = _attached_table_columns(conn, database_name, table_name)
    missing_columns = [column for column in required_columns if column not in available_columns]
    if missing_columns:
        raise ValueError(
            f"Selected database is missing expected columns in {table_name}: {', '.join(missing_columns)}"
        )


def _copy_attached_table(
    conn: sqlite3.Connection,
    table_name: str,
    columns: tuple[str, ...],
    required: bool = True,
) -> None:
    """Copy a table from the attached import database into the current database."""
    if not _attached_table_exists(conn, "import_source", table_name):
        if required:
            raise ValueError(f"Selected database is missing the {table_name} table.")
        return

    available_columns = _attached_table_columns(conn, "import_source", table_name)
    optional_defaults = _OPTIONAL_ATTACHED_COLUMN_DEFAULTS.get(table_name, {})
    select_columns = []
    for column in columns:
        if column in available_columns:
            select_columns.append(column)
        elif column in optional_defaults:
            select_columns.append(f"{optional_defaults[column]} AS {column}")
        else:
            raise ValueError(f"Selected database is missing expected columns in {table_name}: {column}")

    column_list = ", ".join(columns)
    select_list = ", ".join(select_columns)
    conn.execute(
        f"""
        INSERT INTO {table_name} ({column_list})
        SELECT {select_list}
        FROM import_source.{table_name}
        """
    )


def _can_use_fts(query: str) -> bool:
    """Use FTS only for queries that trigram search can handle well."""
    words = [word.strip() for word in query.split() if word.strip()]
    if not words:
        return False

    for word in words:
        stripped = word.strip(string.punctuation)
        if len(stripped) < 3:
            return False

    return True


def _required_attached_columns(table_name: str, columns: tuple[str, ...]) -> tuple[str, ...]:
    """Return the subset of columns that must exist on an attached table."""
    optional_columns = set(_OPTIONAL_ATTACHED_COLUMN_DEFAULTS.get(table_name, {}))
    return tuple(column for column in columns if column not in optional_columns)


def _prepare_snapshot_rows(
    rows: Iterable[Mapping[str, Any]],
    columns: tuple[str, ...],
    optional_defaults: Optional[dict[str, Any]] = None,
) -> list[tuple[Any, ...]]:
    """Normalize externally-provided snapshot rows into ordered column tuples."""
    optional_defaults = optional_defaults or {}
    prepared: list[tuple[Any, ...]] = []

    for row in rows:
        normalized: list[Any] = []
        for column in columns:
            if column in row:
                normalized.append(row[column])
            elif column in optional_defaults:
                normalized.append(optional_defaults[column])
            else:
                raise ValueError(f"Snapshot row is missing required column: {column}")
        prepared.append(tuple(normalized))

    return prepared


def _row_to_snapshot_dict(row: sqlite3.Row, columns: tuple[str, ...]) -> dict[str, Any]:
    """Convert a sqlite row into a plain dict with an explicit column order."""
    return {column: row[column] for column in columns}

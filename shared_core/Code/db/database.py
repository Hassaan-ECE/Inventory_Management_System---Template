"""SQLite database layer for TE Lab Equipment Inventory Manager."""

import sqlite3
import string
import uuid
from pathlib import Path
from typing import Optional

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


def get_connection(db_path: Optional[Path] = None, use_wal: bool = True) -> sqlite3.Connection:
    """Get a SQLite connection with WAL mode and foreign keys enabled."""
    path = db_path or DB_PATH
    conn = sqlite3.connect(str(path))
    conn.execute("PRAGMA journal_mode=WAL" if use_wal else "PRAGMA journal_mode=DELETE")
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
            project_name, picture_path, links, notes, manual_entry, is_archived, source_refs
        ) VALUES (
            ?, ?, ?, ?, ?,
            ?, ?, ?,
            ?, ?, ?, ?, ?,
            ?, ?, ?,
            ?, ?,
            ?, ?, ?,
            ?, ?, ?, ?,
            ?, ?, ?,
            ?, ?, ?, ?, ?
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
    ))
    record_id = cur.lastrowid
    _upsert_equipment_search_row(conn, record_id, eq)
    if commit:
        conn.commit()
    return record_id


def update_equipment(conn: sqlite3.Connection, eq: Equipment, commit: bool = True) -> None:
    """Update an existing equipment record by record_id."""
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
            updated_at=datetime('now')
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
        eq.record_id,
    ))
    _upsert_equipment_search_row(conn, eq.record_id, eq)
    if commit:
        conn.commit()


def delete_equipment(conn: sqlite3.Connection, record_id: int) -> None:
    """Delete an equipment record by record_id."""
    conn.execute("DELETE FROM equipment WHERE record_id=?", (record_id,))
    conn.execute("DELETE FROM equipment_search WHERE record_id=?", (record_id,))
    conn.commit()


def get_equipment_by_id(conn: sqlite3.Connection, record_id: int) -> Optional[Equipment]:
    """Fetch a single equipment record by record_id."""
    row = conn.execute("SELECT * FROM equipment WHERE record_id=?", (record_id,)).fetchone()
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
    rows = conn.execute(
        f"SELECT name FROM {database_name}.pragma_table_info(?)",
        (table_name,),
    ).fetchall()
    return {row[0] for row in rows}


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

"""Characterization tests for snapshot fetch/replace/copy/import behavior."""

from __future__ import annotations

from pathlib import Path

import pytest

from Code.db.database import (
    copy_database_snapshot,
    create_tables,
    fetch_equipment_snapshot,
    fetch_import_issue_snapshot,
    fetch_raw_cell_snapshot,
    get_connection,
    import_database_snapshot,
    insert_equipment,
    insert_import_issue,
    insert_raw_cells_batch,
    load_sync_state,
    replace_local_snapshot,
    search_equipment,
)
from Code.db.models import Equipment, ImportIssue, RawCell


def _seed_source_db(source_path: Path) -> None:
    conn = get_connection(source_path)
    try:
        create_tables(conn)
        insert_equipment(
            conn,
            Equipment(
                record_uuid="snap-1",
                asset_number="SNAP-001",
                serial_number="SER-001",
                manufacturer="Fluke",
                model="289",
                description="Source snapshot row",
            ),
        )
        insert_import_issue(
            conn,
            ImportIssue(
                issue_type="duplicate",
                source_file="Master.xlsx",
                source_sheet="All Equip",
                source_row=12,
                summary="Duplicate asset number",
            ),
        )
        insert_raw_cells_batch(
            conn,
            [
                RawCell(
                    source_file="Master.xlsx",
                    source_sheet="All Equip",
                    row_number=12,
                    column_number=3,
                    cell_address="C12",
                    cell_value="SNAP-001",
                    row_preview="SNAP-001,Fluke,289",
                )
            ],
        )
    finally:
        conn.close()


def test_replace_local_snapshot_from_payloads_preserves_counts_and_revision(tmp_path: Path) -> None:
    source_path = tmp_path / "source.db"
    target_path = tmp_path / "target.db"
    _seed_source_db(source_path)

    source_conn = get_connection(source_path)
    target_conn = get_connection(target_path)
    try:
        create_tables(source_conn)
        create_tables(target_conn)

        stats = replace_local_snapshot(
            target_conn,
            fetch_equipment_snapshot(source_conn),
            fetch_import_issue_snapshot(source_conn),
            raw_cell_snapshot=fetch_raw_cell_snapshot(source_conn),
            tombstone_snapshot=[],
            revision="7",
            equipment_snapshot_hash="eq_hash",
            import_issue_snapshot_hash="issue_hash",
            global_mutation_at="2026-01-01T00:00:00Z",
            clear_outbox=True,
            clear_applied_ops=True,
            commit=True,
        )

        assert stats["equipment_records"] == 1
        assert stats["raw_cells"] == 1
        assert stats["import_issues"] == 1
        state = load_sync_state(target_conn)
        assert state["revision"] == "7"
    finally:
        source_conn.close()
        target_conn.close()


def test_copy_database_snapshot_replaces_target_database(tmp_path: Path) -> None:
    source_path = tmp_path / "copy_source.db"
    target_path = tmp_path / "copy_target.db"
    _seed_source_db(source_path)

    stats = copy_database_snapshot(target_path, source_path, clear_outbox=True, clear_applied_ops=True)
    assert stats["equipment_records"] == 1
    assert stats["raw_cells"] == 1
    assert stats["import_issues"] == 1

    target_conn = get_connection(target_path)
    try:
        rows = search_equipment(target_conn, "SNAP-001", archived="all")
        assert len(rows) == 1
        assert rows[0].record_uuid == "snap-1"
    finally:
        target_conn.close()


def test_import_database_snapshot_replaces_current_connection_data(tmp_path: Path) -> None:
    source_path = tmp_path / "import_source.db"
    app_db_path = tmp_path / "app.db"
    _seed_source_db(source_path)

    app_conn = get_connection(app_db_path)
    try:
        create_tables(app_conn)
        insert_equipment(
            app_conn,
            Equipment(
                record_uuid="local-old",
                asset_number="LOCAL-ONLY",
                serial_number="LOCAL-0001",
                manufacturer="Legacy",
                model="X",
            ),
        )

        stats = import_database_snapshot(app_conn, source_path)
        assert stats["equipment_records"] == 1
        rows = search_equipment(app_conn, "SNAP-001", archived="all")
        assert len(rows) == 1
        assert rows[0].record_uuid == "snap-1"

        local_rows = search_equipment(app_conn, "LOCAL-ONLY", archived="all")
        assert local_rows == []
    finally:
        app_conn.close()

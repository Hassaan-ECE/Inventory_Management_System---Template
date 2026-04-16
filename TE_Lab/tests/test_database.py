"""Database-layer regression tests."""

import sqlite3
import tempfile
import unittest
from pathlib import Path

from Code.db.database import (
    create_tables,
    get_connection,
    import_database_snapshot,
    get_equipment_stats,
    insert_equipment,
    insert_import_issue,
    search_equipment,
)
from Code.db.models import Equipment, ImportIssue


class DatabaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test.db"
        self.conn = get_connection(self.db_path)
        create_tables(self.conn)

    def tearDown(self) -> None:
        self.conn.close()
        self.temp_dir.cleanup()

    def test_search_equipment_applies_column_filters_in_sql(self) -> None:
        insert_equipment(
            self.conn,
            Equipment(
                asset_number="A-100",
                manufacturer="Fluke",
                manufacturer_raw="Fluke",
                model="87V",
                description="Digital Multimeter",
                location="TE Lab",
                lifecycle_status="active",
                working_status="working",
                calibration_status="calibrated",
                estimated_age_years=10.5,
            ),
        )
        insert_equipment(
            self.conn,
            Equipment(
                asset_number="A-200",
                manufacturer="Keysight",
                manufacturer_raw="Keysight",
                model="34461A",
                description="Bench Meter",
                location="Storage",
                lifecycle_status="repair",
                working_status="limited",
                calibration_status="reference_only",
                estimated_age_years=5.0,
            ),
        )

        results = search_equipment(
            self.conn,
            "meter",
            manufacturer="Keysight",
            lifecycle="repair",
            calibration="reference_only",
            working="limited",
            location="Storage",
            asset_number="A-200",
            model="3446",
            description="Bench",
            estimated_age_years="5",
        )

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].asset_number, "A-200")

    def test_get_equipment_stats_returns_expected_counts(self) -> None:
        insert_equipment(
            self.conn,
            Equipment(
                asset_number="A-100",
                lifecycle_status="active",
                calibration_status="calibrated",
                verified_in_survey=True,
            ),
        )
        insert_equipment(
            self.conn,
            Equipment(
                asset_number="A-200",
                lifecycle_status="repair",
                calibration_status="reference_only",
            ),
        )
        insert_equipment(
            self.conn,
            Equipment(
                asset_number="A-300",
                lifecycle_status="missing",
                calibration_status="unknown",
            ),
        )
        insert_import_issue(
            self.conn,
            ImportIssue(issue_type="duplicate", summary="duplicate id"),
        )

        stats = get_equipment_stats(self.conn)

        self.assertEqual(stats["total"], 3)
        self.assertEqual(stats["active"], 1)
        self.assertEqual(stats["repair"], 1)
        self.assertEqual(stats["missing"], 1)
        self.assertEqual(stats["calibrated"], 1)
        self.assertEqual(stats["reference_only"], 1)
        self.assertEqual(stats["verified_in_survey"], 1)
        self.assertEqual(stats["archived"], 0)
        self.assertEqual(stats["import_issues"], 1)

    def test_search_equipment_can_switch_between_inventory_and_archive_scopes(self) -> None:
        insert_equipment(
            self.conn,
            Equipment(
                asset_number="INV-100",
                manufacturer="Fixture Cart",
                manufacturer_raw="Fixture Cart",
                description="Current cart",
            ),
        )
        insert_equipment(
            self.conn,
            Equipment(
                asset_number="ARC-100",
                manufacturer="Fixture Cart",
                manufacturer_raw="Fixture Cart",
                description="Retired cart",
                is_archived=True,
            ),
        )

        active_results = search_equipment(self.conn, "cart")
        archived_results = search_equipment(self.conn, "cart", archived="archived")
        all_results = search_equipment(self.conn, "cart", archived="all")

        self.assertEqual([row.asset_number for row in active_results], ["INV-100"])
        self.assertEqual([row.asset_number for row in archived_results], ["ARC-100"])
        self.assertEqual([row.asset_number for row in all_results], ["ARC-100", "INV-100"])

    def test_get_equipment_stats_can_report_archive_counts(self) -> None:
        insert_equipment(
            self.conn,
            Equipment(
                asset_number="INV-200",
                description="Current fixture",
            ),
        )
        insert_equipment(
            self.conn,
            Equipment(
                asset_number="ARC-200",
                description="Archived fixture",
                is_archived=True,
            ),
        )

        stats = get_equipment_stats(self.conn)
        active_stats = get_equipment_stats(self.conn, archived="active")

        self.assertEqual(stats["total"], 2)
        self.assertEqual(stats["archived"], 1)
        self.assertEqual(active_stats["total"], 1)
        self.assertEqual(active_stats["archived"], 0)

    def test_search_equipment_uses_fts_index_for_long_queries(self) -> None:
        insert_equipment(
            self.conn,
            Equipment(
                asset_number="A-100",
                manufacturer="Fluke",
                manufacturer_raw="Fluke",
                model="87V",
                description="Digital Multimeter",
            ),
        )

        results = search_equipment(self.conn, "multimeter")

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].asset_number, "A-100")

    def test_search_index_stays_in_sync_on_update_and_delete(self) -> None:
        record_id = insert_equipment(
            self.conn,
            Equipment(
                asset_number="A-100",
                manufacturer="Fluke",
                manufacturer_raw="Fluke",
                model="87V",
                description="Digital Multimeter",
            ),
        )

        eq = self.conn.execute("SELECT * FROM equipment WHERE record_id=?", (record_id,)).fetchone()
        self.assertIsNotNone(eq)

        from Code.db.database import delete_equipment, get_equipment_by_id, update_equipment

        equipment = get_equipment_by_id(self.conn, record_id)
        self.assertIsNotNone(equipment)
        equipment.description = "Bench Oscilloscope"
        update_equipment(self.conn, equipment)

        self.assertEqual(len(search_equipment(self.conn, "multimeter")), 0)
        self.assertEqual(len(search_equipment(self.conn, "oscilloscope")), 1)

        delete_equipment(self.conn, record_id)
        self.assertEqual(len(search_equipment(self.conn, "oscilloscope")), 0)

    def test_search_equipment_falls_back_for_short_queries(self) -> None:
        insert_equipment(
            self.conn,
            Equipment(
                asset_number="A-100",
                manufacturer="HP",
                manufacturer_raw="HP",
                model="34401A",
                description="Bench Meter",
            ),
        )

        results = search_equipment(self.conn, "hp")

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].manufacturer, "HP")

    def test_search_equipment_matches_short_model_substrings(self) -> None:
        insert_equipment(
            self.conn,
            Equipment(
                asset_number="A-100",
                manufacturer="LeCroy",
                manufacturer_raw="LeCroy",
                model="LT264M",
                description="Digital Oscilloscope",
            ),
        )

        results = search_equipment(self.conn, "4M")

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].model, "LT264M")

    def test_import_database_snapshot_copies_equipment_and_issues(self) -> None:
        source_path = Path(self.temp_dir.name) / "source.db"
        source_conn = get_connection(source_path)
        create_tables(source_conn)
        try:
            insert_equipment(
                source_conn,
                Equipment(
                    asset_number="SRC-100",
                    manufacturer="Fluke",
                    manufacturer_raw="Fluke",
                    model="87V",
                    description="Shared multimeter",
                    verified_in_survey=True,
                    manual_entry=True,
                ),
            )
            insert_import_issue(
                source_conn,
                ImportIssue(issue_type="duplicate", summary="duplicate asset number"),
            )
        finally:
            source_conn.close()

        insert_equipment(
            self.conn,
            Equipment(
                asset_number="LOCAL-1",
                description="Should be replaced",
            ),
        )

        stats = import_database_snapshot(self.conn, source_path)
        imported = search_equipment(self.conn, "shared")

        self.assertEqual(stats["equipment_records"], 1)
        self.assertEqual(stats["import_issues"], 1)
        self.assertEqual(len(imported), 1)
        self.assertEqual(imported[0].asset_number, "SRC-100")
        self.assertEqual(search_equipment(self.conn, "replaced"), [])

    def test_import_database_snapshot_rebuilds_local_copy(self) -> None:
        source_path = Path(self.temp_dir.name) / "portable.db"
        source_conn = get_connection(source_path)
        create_tables(source_conn)
        try:
            insert_equipment(
                source_conn,
                Equipment(
                    asset_number="PORT-200",
                    manufacturer="Keysight",
                    manufacturer_raw="Keysight",
                    model="34461A",
                    description="Portable source copy",
                ),
            )
        finally:
            source_conn.close()

        import_database_snapshot(self.conn, source_path)
        source_path.unlink()

        results = search_equipment(self.conn, "portable")

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].asset_number, "PORT-200")

    def test_create_tables_upgrades_legacy_database_without_archive_column(self) -> None:
        legacy_path = Path(self.temp_dir.name) / "legacy.db"
        legacy_conn = sqlite3.connect(str(legacy_path))
        try:
            legacy_conn.executescript("""
                CREATE TABLE equipment (
                    record_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    asset_number TEXT DEFAULT '',
                    serial_number TEXT DEFAULT '',
                    manufacturer TEXT DEFAULT '',
                    manufacturer_raw TEXT DEFAULT '',
                    model TEXT DEFAULT '',
                    description TEXT DEFAULT '',
                    qty REAL,
                    location TEXT DEFAULT '',
                    assigned_to TEXT DEFAULT '',
                    ownership_type TEXT DEFAULT 'owned',
                    rental_vendor TEXT DEFAULT '',
                    rental_cost_monthly REAL,
                    calibration_status TEXT DEFAULT 'unknown',
                    last_calibration_date TEXT DEFAULT '',
                    calibration_due_date TEXT DEFAULT '',
                    calibration_vendor TEXT DEFAULT '',
                    calibration_cost REAL,
                    lifecycle_status TEXT DEFAULT 'active',
                    working_status TEXT DEFAULT 'unknown',
                    condition TEXT DEFAULT '',
                    acquired_date TEXT DEFAULT '',
                    estimated_age_years REAL,
                    age_basis TEXT DEFAULT 'unknown',
                    verified_in_survey INTEGER DEFAULT 0,
                    blue_dot_ref TEXT DEFAULT '',
                    notes TEXT DEFAULT '',
                    manual_entry INTEGER DEFAULT 0,
                    source_refs TEXT DEFAULT '[]',
                    created_at TEXT DEFAULT (datetime('now')),
                    updated_at TEXT DEFAULT (datetime('now')),
                    picture_path TEXT DEFAULT '',
                    project_name TEXT DEFAULT '',
                    links TEXT DEFAULT ''
                );
                CREATE TABLE raw_cells (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_file TEXT,
                    source_sheet TEXT,
                    row_number INTEGER,
                    column_number INTEGER,
                    cell_address TEXT,
                    cell_value TEXT,
                    row_preview TEXT
                );
                CREATE TABLE import_issues (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    issue_type TEXT,
                    source_file TEXT,
                    source_sheet TEXT,
                    source_row INTEGER,
                    asset_number TEXT DEFAULT '',
                    serial_number TEXT DEFAULT '',
                    summary TEXT,
                    raw_data TEXT DEFAULT '{}',
                    resolution_status TEXT DEFAULT 'unresolved',
                    created_at TEXT DEFAULT (datetime('now'))
                );
            """)
            legacy_conn.commit()
        finally:
            legacy_conn.close()

        upgraded_conn = get_connection(legacy_path)
        try:
            create_tables(upgraded_conn)
            columns = {
                row["name"]
                for row in upgraded_conn.execute("PRAGMA table_info(equipment)").fetchall()
            }
            indexes = {
                row["name"]
                for row in upgraded_conn.execute("PRAGMA index_list(equipment)").fetchall()
            }
        finally:
            upgraded_conn.close()

        self.assertIn("is_archived", columns)
        self.assertIn("idx_equipment_archived", indexes)


if __name__ == "__main__":
    unittest.main()

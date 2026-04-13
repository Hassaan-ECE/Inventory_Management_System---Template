"""Regression tests for import safety and duplicate-aware matching."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from Code.db.database import create_tables, get_connection, insert_equipment
from Code.db.models import Equipment, ImportIssue, RawCell
from Code.importer.matching import build_equipment_indexes, resolve_equipment_match
from Code.importer.pipeline import run_full_import, run_merge_import


MASTER_FILE = "Master List of Eng.Equipment - All - 2020.RO.xls"
SURVEY_FILE = "Survey oF Equip In Eng Lab.xlsx"


class ImportPipelineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.temp_dir.name)
        (self.data_dir / MASTER_FILE).write_bytes(b"")
        (self.data_dir / SURVEY_FILE).write_bytes(b"")
        self.db_path = self.data_dir / "test.db"

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_resolve_equipment_match_flags_duplicate_conflicts(self) -> None:
        records = [
            Equipment(asset_number="A-1", serial_number="S-1"),
            Equipment(asset_number="A-1", serial_number="S-1"),
        ]
        by_asset, by_serial, by_import_key = build_equipment_indexes(records)

        match = resolve_equipment_match(by_asset, by_serial, by_import_key, "A-1", "S-1")

        self.assertIsNone(match.record)
        self.assertEqual(match.status, "conflict")
        self.assertIn("matches multiple base records", match.summary)

    def test_resolve_equipment_match_uses_unique_serial_to_break_asset_tie(self) -> None:
        records = [
            Equipment(asset_number="A-1", serial_number="S-1"),
            Equipment(asset_number="A-1", serial_number="S-2"),
        ]
        by_asset, by_serial, by_import_key = build_equipment_indexes(records)

        match = resolve_equipment_match(by_asset, by_serial, by_import_key, "A-1", "S-2")

        self.assertIs(match.record, records[1])
        self.assertEqual(match.status, "matched")

    def test_run_full_import_marks_survey_matches_as_verified(self) -> None:
        def fake_base_sheet(_path: Path):
            return ([self._equipment("A-1", "S-1", row=2)], [])

        survey_rows = [{
            "asset_number": "A-1",
            "serial_number": "S-1",
            "manufacturer": "Acme",
            "model": "Model 1",
            "description": "Widget",
            "location": "Lab 1",
            "blue_dot": "BD-1",
            "how_old": "5",
            "section": "may_2025_cal",
            "source_row": 12,
        }]

        with patch("Code.importer.pipeline.parse_base_sheet", side_effect=fake_base_sheet), \
             patch("Code.importer.pipeline.parse_overlay_sheets", side_effect=lambda _p, records: (records, [])), \
             patch("Code.importer.pipeline.parse_survey", return_value=(survey_rows, [])), \
             patch("Code.importer.pipeline.index_all_raw_cells", return_value=[]), \
             patch("Code.importer.pipeline.index_survey_raw_cells", return_value=[]):
            run_full_import(self.data_dir, db_path=self.db_path)

        conn = get_connection(self.db_path)
        try:
            verified = conn.execute(
                "SELECT verified_in_survey, blue_dot_ref, estimated_age_years, age_basis, source_refs "
                "FROM equipment"
            ).fetchone()
        finally:
            conn.close()

        self.assertEqual(verified["verified_in_survey"], 1)
        self.assertEqual(verified["blue_dot_ref"], "BD-1")
        self.assertEqual(verified["estimated_age_years"], 5.0)
        self.assertEqual(verified["age_basis"], "survey")
        self.assertIn("Survey oF Equip In Eng Lab.xlsx", verified["source_refs"])

    def test_run_full_import_rolls_back_failed_reimport(self) -> None:
        self._run_successful_import()

        conn = get_connection(self.db_path)
        try:
            before = self._counts(conn)
        finally:
            conn.close()

        with patch("Code.importer.pipeline.parse_base_sheet", side_effect=RuntimeError("boom")):
            with self.assertRaisesRegex(RuntimeError, "boom"):
                run_full_import(self.data_dir, db_path=self.db_path)

        conn = get_connection(self.db_path)
        try:
            after = self._counts(conn)
        finally:
            conn.close()

        self.assertEqual(after, before)

    def test_run_full_import_rolls_back_late_failures(self) -> None:
        self._run_successful_import()

        conn = get_connection(self.db_path)
        try:
            before = self._counts(conn)
        finally:
            conn.close()

        with patch("Code.importer.pipeline.parse_base_sheet", side_effect=self._fake_base_sheet), \
             patch("Code.importer.pipeline.parse_overlay_sheets", side_effect=lambda _p, records: (records, [])), \
             patch("Code.importer.pipeline.parse_survey", return_value=([], [])), \
             patch("Code.importer.pipeline.index_all_raw_cells", return_value=[]), \
             patch("Code.importer.pipeline.index_survey_raw_cells", side_effect=RuntimeError("late boom")):
            with self.assertRaisesRegex(RuntimeError, "late boom"):
                run_full_import(self.data_dir, db_path=self.db_path)

        conn = get_connection(self.db_path)
        try:
            after = self._counts(conn)
        finally:
            conn.close()

        self.assertEqual(after, before)

    def test_run_merge_import_adds_new_records_without_overwriting_current_values(self) -> None:
        conn = get_connection(self.db_path)
        create_tables(conn)
        try:
            insert_equipment(
                conn,
                Equipment(
                    asset_number="A-1",
                    serial_number="S-1",
                    manufacturer="CurrentCo",
                    manufacturer_raw="CurrentCo",
                    model="Current Model",
                    description="Current description",
                    location="Current Lab",
                ),
            )
        finally:
            conn.close()

        imported_records = [
            self._equipment("A-1", "S-1", row=2),
            self._equipment("A-2", "S-2", row=3),
        ]
        imported_records[0].description = "Old description"
        imported_records[0].location = ""
        imported_records[1].description = "Older inventory row"

        with patch("Code.importer.pipeline.parse_base_sheet", return_value=(imported_records, [])), \
             patch("Code.importer.pipeline.parse_overlay_sheets", side_effect=lambda _p, records: (records, [])), \
             patch("Code.importer.pipeline.parse_survey", return_value=([], [])), \
             patch("Code.importer.pipeline.index_all_raw_cells", return_value=[]), \
             patch("Code.importer.pipeline.index_survey_raw_cells", return_value=[]):
            stats = run_merge_import(self.data_dir, db_path=self.db_path)

        conn = get_connection(self.db_path)
        try:
            rows = conn.execute(
                "SELECT asset_number, description, location, source_refs FROM equipment ORDER BY asset_number"
            ).fetchall()
        finally:
            conn.close()

        self.assertEqual(stats["added_records"], 1)
        self.assertEqual(stats["matched_records"], 1)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["asset_number"], "A-1")
        self.assertEqual(rows[0]["description"], "Current description")
        self.assertEqual(rows[0]["location"], "Current Lab")
        self.assertIn(MASTER_FILE, rows[0]["source_refs"])
        self.assertEqual(rows[1]["asset_number"], "A-2")
        self.assertEqual(rows[1]["description"], "Older inventory row")

    def test_run_merge_import_replaces_previous_excel_artifacts(self) -> None:
        base_issue = ImportIssue(
            issue_type="missing_id",
            source_file=MASTER_FILE,
            source_sheet="All Equip",
            source_row=2,
            summary="Row 2: no asset number and no serial number",
        )
        master_cells = [
            RawCell(
                source_file=MASTER_FILE,
                source_sheet="All Equip",
                row_number=2,
                column_number=1,
                cell_address="A2",
                cell_value="A-1",
                row_preview="A-1 | S-1",
            )
        ]

        with patch("Code.importer.pipeline.parse_base_sheet", side_effect=self._fake_base_sheet), \
             patch("Code.importer.pipeline.parse_overlay_sheets", side_effect=lambda _p, records: (records, [])), \
             patch("Code.importer.pipeline.parse_survey", return_value=([], [])), \
             patch("Code.importer.pipeline.index_all_raw_cells", return_value=master_cells), \
             patch("Code.importer.pipeline.index_survey_raw_cells", return_value=[]):
            run_merge_import(self.data_dir, db_path=self.db_path)

        with patch("Code.importer.pipeline.parse_base_sheet", return_value=([self._equipment("A-1", "S-1", row=2)], [base_issue])), \
             patch("Code.importer.pipeline.parse_overlay_sheets", side_effect=lambda _p, records: (records, [])), \
             patch("Code.importer.pipeline.parse_survey", return_value=([], [])), \
             patch("Code.importer.pipeline.index_all_raw_cells", return_value=master_cells), \
             patch("Code.importer.pipeline.index_survey_raw_cells", return_value=[]):
            run_merge_import(self.data_dir, db_path=self.db_path)

        conn = get_connection(self.db_path)
        try:
            counts = self._counts(conn)
            raw_cell_count = conn.execute("SELECT COUNT(*) FROM raw_cells WHERE source_file=?", (MASTER_FILE,)).fetchone()[0]
            issue_count = conn.execute("SELECT COUNT(*) FROM import_issues WHERE source_file=?", (MASTER_FILE,)).fetchone()[0]
        finally:
            conn.close()

        self.assertEqual(counts[0], 1)
        self.assertEqual(raw_cell_count, 1)
        self.assertEqual(issue_count, 1)

    def test_resolve_equipment_match_uses_import_key_when_ids_are_blank(self) -> None:
        record = Equipment(
            manufacturer="Cart",
            source_refs=json.dumps([{
                "file": MASTER_FILE,
                "sheet": "Mfg Material",
                "row": 2,
                "import_key": "me::mfg_material::1",
            }]),
        )
        by_asset, by_serial, by_import_key = build_equipment_indexes([record])

        match = resolve_equipment_match(
            by_asset,
            by_serial,
            by_import_key,
            import_key="me::mfg_material::1",
        )

        self.assertIs(match.record, record)
        self.assertEqual(match.status, "matched")

    def _run_successful_import(self) -> None:
        with patch("Code.importer.pipeline.parse_base_sheet", side_effect=self._fake_base_sheet), \
             patch("Code.importer.pipeline.parse_overlay_sheets", side_effect=lambda _p, records: (records, [])), \
             patch("Code.importer.pipeline.parse_survey", return_value=([], [])), \
             patch("Code.importer.pipeline.index_all_raw_cells", return_value=[]), \
             patch("Code.importer.pipeline.index_survey_raw_cells", return_value=[]):
            run_full_import(self.data_dir, db_path=self.db_path)

    def _fake_base_sheet(self, _path: Path):
        return ([self._equipment("A-1", "S-1", row=2)], [])

    def _equipment(self, asset_number: str, serial_number: str, row: int) -> Equipment:
        return Equipment(
            asset_number=asset_number,
            serial_number=serial_number,
            manufacturer="Acme",
            model="Model 1",
            source_refs=json.dumps([{
                "file": MASTER_FILE,
                "sheet": "All Equip",
                "row": row,
            }]),
        )

    def _counts(self, conn) -> tuple[int, int, int]:
        return (
            conn.execute("SELECT COUNT(*) FROM equipment").fetchone()[0],
            conn.execute("SELECT COUNT(*) FROM raw_cells").fetchone()[0],
            conn.execute("SELECT COUNT(*) FROM import_issues").fetchone()[0],
        )


if __name__ == "__main__":
    unittest.main()

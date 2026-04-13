"""Regression tests for the ME single-workbook import flow."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from openpyxl import Workbook

from Code.db.database import get_connection
from Code.importer.pipeline import run_full_import, run_merge_import


MASTER_FILE = "Machine Shop Material list.xlsx"


class MEImportPipelineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.temp_dir.name)
        self.db_path = self.data_dir / "test.db"
        self.workbook_path = self.data_dir / MASTER_FILE

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_run_full_import_loads_rows_from_both_sheets(self) -> None:
        self._write_workbook(qty="2", second_qty="5")

        stats = run_full_import(self.data_dir, db_path=self.db_path)

        conn = get_connection(self.db_path)
        try:
            count = conn.execute("SELECT COUNT(*) FROM equipment").fetchone()[0]
            raw_cells = conn.execute("SELECT COUNT(*) FROM raw_cells").fetchone()[0]
            rows = conn.execute(
                "SELECT manufacturer, description, qty, location, source_refs "
                "FROM equipment ORDER BY record_id"
            ).fetchall()
        finally:
            conn.close()

        self.assertEqual(stats["base_records"], 2)
        self.assertEqual(count, 2)
        self.assertGreater(raw_cells, 0)
        self.assertEqual(rows[0]["manufacturer"], "Roller Cart")
        self.assertEqual(rows[1]["manufacturer"], "Metal Enclosure")
        self.assertIn("import_key", rows[0]["source_refs"])

    def test_run_merge_import_updates_existing_me_rows_without_duplication(self) -> None:
        self._write_workbook(qty="2", second_qty="5")
        run_full_import(self.data_dir, db_path=self.db_path)

        self._write_workbook(qty="7", second_qty="5")
        stats = run_merge_import(self.data_dir, db_path=self.db_path)

        conn = get_connection(self.db_path)
        try:
            count = conn.execute("SELECT COUNT(*) FROM equipment").fetchone()[0]
            qty = conn.execute(
                "SELECT qty FROM equipment WHERE manufacturer='Roller Cart'"
            ).fetchone()[0]
        finally:
            conn.close()

        self.assertEqual(count, 2)
        self.assertEqual(stats["matched_records"], 2)
        self.assertEqual(qty, 2.0)

    def test_run_merge_import_adds_new_me_rows(self) -> None:
        self._write_workbook(qty="2", second_qty="5")
        run_full_import(self.data_dir, db_path=self.db_path)

        self._write_workbook(qty="2", second_qty="5", include_third=True)
        stats = run_merge_import(self.data_dir, db_path=self.db_path)

        conn = get_connection(self.db_path)
        try:
            count = conn.execute("SELECT COUNT(*) FROM equipment").fetchone()[0]
        finally:
            conn.close()

        self.assertEqual(count, 3)
        self.assertEqual(stats["added_records"], 1)

    def test_run_full_import_uses_me_profile(self) -> None:
        self._write_workbook(qty="2", second_qty="5")

        with patch("Code.importer.pipeline._import_profile", return_value="me_single_workbook"):
            stats = run_full_import(self.data_dir, db_path=self.db_path)

        self.assertEqual(stats["base_records"], 2)

    def _write_workbook(self, qty: str, second_qty: str, include_third: bool = False) -> None:
        wb = Workbook()
        lotus = wb.active
        lotus.title = "Lotus building material "
        lotus.append(["Machine shop Material List"])
        lotus.append([
            "Item no. ",
            "Material name ",
            "Description ",
            "Purpouse ",
            "Asset Tag ID",
            "Model",
            "Serial Number",
            "Quantity",
            "Location ",
            "Picture ",
        ])
        lotus.append([1, "Roller Cart", "Shop cart", "Fixtures", "N/A", "", "", qty, "3460", ""])

        mfg = wb.create_sheet("Mfg Material")
        mfg.append(["TE Team Machine shop Material List"])
        mfg.append([
            "Item no. ",
            "Material name ",
            "Description ",
            "Quantity",
            "Location ",
            "Picture ",
            "BOX No. ",
            "MODEL No. ",
        ])
        mfg.append([1, "Metal Enclosure", "Line enclosure", second_qty, "Engineering Storage", "", "B-2", "SPT-504025"])
        if include_third:
            mfg.append([2, "Ultrasonic Cleaner", "Cleaner", "1", "Engineering Storage", "", "", "KSTH-100A"])
        wb.save(self.workbook_path)


if __name__ == "__main__":
    unittest.main()

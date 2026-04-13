"""Starter smoke test for the ME inventory app."""

import tempfile
import unittest
from pathlib import Path

from PySide6.QtWidgets import QHeaderView
from PySide6.QtWidgets import QApplication

from Code.db.database import create_tables, get_connection
from Code.gui.main_window import MainWindow, active_filter_specs
from Code.gui.equipment_table import DATA_COL_START


class MainWindowSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test.db"
        self.conn = get_connection(self.db_path)
        create_tables(self.conn)

    def tearDown(self) -> None:
        self.conn.close()
        self.temp_dir.cleanup()

    def test_window_can_be_created_against_empty_database(self) -> None:
        window = MainWindow(self.conn)
        try:
            self.assertEqual(window.windowTitle(), "ME Lab Inventory")
            headers = [
                window.table.horizontalHeaderItem(index).text()
                for index in range(window.table.columnCount())
            ]
            self.assertEqual(
                headers,
                ["✓", "Asset #", "Qty", "Manufacturer", "Model", "Description", "Location"],
            )
            self.assertTrue(window.table.isColumnHidden(DATA_COL_START))
            self.assertNotIn("Est. Age (Yrs)", headers)
            self.assertNotIn("Status", headers)
            self.assertNotIn("Calibration", headers)
            self.assertEqual(
                [field for _, field, _ in active_filter_specs()],
                ["asset_number", "manufacturer", "model", "description", "location"],
            )
        finally:
            window.close()

    def test_description_column_keeps_interactive_resize_handle(self) -> None:
        window = MainWindow(self.conn)
        try:
            headers = [
                window.table.horizontalHeaderItem(index).text()
                for index in range(window.table.columnCount())
            ]
            description_index = headers.index("Description")
            self.assertEqual(
                window.table.horizontalHeader().sectionResizeMode(description_index),
                QHeaderView.Interactive,
            )
        finally:
            window.close()

    def test_last_visible_column_stretches_to_fill_table_width(self) -> None:
        window = MainWindow(self.conn)
        try:
            self.assertTrue(window.table.horizontalHeader().stretchLastSection())
        finally:
            window.close()


if __name__ == "__main__":
    unittest.main()

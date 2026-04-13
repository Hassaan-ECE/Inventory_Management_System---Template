"""Regression tests for MainWindow interactions."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QDialog

from Code.db.database import create_tables, get_connection, get_equipment_by_id, insert_equipment
from Code.db.models import Equipment
from Code.gui.equipment_table import COLUMNS, DATA_COL_START
from Code.gui.main_window import MainWindow


class _AcceptedDialog:
    def __init__(self, *args, **kwargs) -> None:
        self._value = kwargs.get("current_value", "")

    def exec(self) -> int:
        return QDialog.Accepted

    def value(self) -> str:
        return "12.5"


class MainWindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test.db"
        self.conn = get_connection(self.db_path)
        create_tables(self.conn)
        self.record_id = insert_equipment(
            self.conn,
            Equipment(
                asset_number="A-100",
                manufacturer="Fluke",
                manufacturer_raw="Fluke",
                model="87V",
                description="Digital Multimeter",
                estimated_age_years=None,
            ),
        )
        self.window = MainWindow(self.conn)

    def tearDown(self) -> None:
        self.window.close()
        self.conn.close()
        self.temp_dir.cleanup()

    def test_quick_edit_age_updates_record(self) -> None:
        age_column = DATA_COL_START + next(
            index for index, (_, field, _) in enumerate(COLUMNS)
            if field == "estimated_age_years"
        )

        with patch("Code.gui.main_window.QuickEditDialog", _AcceptedDialog):
            self.window._quick_edit_cell(0, age_column)

        eq = get_equipment_by_id(self.conn, self.record_id)
        self.assertIsNotNone(eq)
        self.assertEqual(eq.estimated_age_years, 12.5)
        self.assertEqual(eq.age_basis, "estimated_manual")


if __name__ == "__main__":
    unittest.main()

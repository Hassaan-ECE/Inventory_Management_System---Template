"""Starter smoke test for a new inventory app variant."""

import tempfile
import unittest
from pathlib import Path

from PySide6.QtWidgets import QApplication

from Code.db.database import create_tables, get_connection
from Code.gui.main_window import MainWindow


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
            self.assertEqual(window.windowTitle(), "Lab Inventory")
        finally:
            window.close()


if __name__ == "__main__":
    unittest.main()

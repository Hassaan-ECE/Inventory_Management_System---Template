"""Dialog tests for the ME picture workflow."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication

from Code.db.database import create_tables, get_connection
from Code.gui.add_edit_dialog import AddEditDialog


class AddEditDialogPictureTests(unittest.TestCase):
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

    def test_me_dialog_uses_picture_section_and_builds_picture_payload(self) -> None:
        dialog = AddEditDialog(self.conn)
        try:
            self.assertTrue(hasattr(dialog, "picture_path_input"))
            self.assertFalse(hasattr(dialog, "cal_status_combo"))
            self.assertTrue(hasattr(dialog, "project_input"))
            self.assertTrue(hasattr(dialog, "qty_input"))
            self.assertFalse(hasattr(dialog, "age_input"))
            self.assertFalse(hasattr(dialog, "lifecycle_combo"))
            self.assertFalse(hasattr(dialog, "ownership_combo"))
            self.assertTrue(hasattr(dialog, "picture_browse_btn"))
            self.assertFalse(hasattr(dialog, "picture_clear_btn"))

            dialog.asset_input.setText("ME-100")
            dialog.manufacturer_input.setText("Fixture Cart")
            dialog.qty_input.setText("4")
            dialog.project_input.setText("AALC Line Upgrade")
            dialog.description_input.setText("Fixture storage cart")
            dialog.links_input.setText("https://vendor.example/fixture-cart")
            dialog.picture_path_input.setText(r"C:\images\fixture-cart.png")

            dialog._on_save()
            payload = dialog.get_save_payload()

            self.assertIsNotNone(payload)
            self.assertEqual(payload["action"], "insert")
            equipment = payload["equipment"]
            self.assertEqual(equipment.picture_path, r"C:\images\fixture-cart.png")
            self.assertEqual(equipment.calibration_status, "unknown")
            self.assertEqual(equipment.qty, 4.0)
            self.assertEqual(equipment.project_name, "AALC Line Upgrade")
            self.assertEqual(equipment.links, "https://vendor.example/fixture-cart")

            row = self.conn.execute(
                "SELECT COUNT(*) FROM equipment WHERE asset_number='ME-100'"
            ).fetchone()
            self.assertEqual(row[0], 0)

            dialog.picture_path_input.clear()
            self.assertEqual(dialog.picture_preview.text(), "No picture selected")
        finally:
            dialog.close()

    def test_me_dialog_opens_picture_with_system_viewer(self) -> None:
        dialog = AddEditDialog(self.conn)
        try:
            picture_path = Path(self.temp_dir.name) / "fixture.png"
            picture_path.write_bytes(b"fake-image-bytes")
            dialog.picture_path_input.setText(str(picture_path))

            with patch("Code.gui.add_edit_dialog.QDesktopServices.openUrl", return_value=True) as open_url:
                opened = dialog._open_picture_in_viewer()

            self.assertTrue(opened)
            open_url.assert_called_once()
            self.assertEqual(
                Path(open_url.call_args.args[0].toLocalFile()).resolve(),
                picture_path.resolve(),
            )
        finally:
            dialog.close()

    def test_me_dialog_refreshes_picture_preview_after_show(self) -> None:
        picture_path = Path(self.temp_dir.name) / "fixture.png"
        picture_path.write_bytes(b"fake-image-bytes")
        dialog = AddEditDialog(self.conn)
        try:
            dialog.picture_path_input.setText(str(picture_path))

            with patch.object(dialog, "_update_picture_preview", wraps=dialog._update_picture_preview) as refresh:
                dialog.show()
                self.app.processEvents()

            refresh.assert_called_with(str(picture_path))
        finally:
            dialog.close()


if __name__ == "__main__":
    unittest.main()

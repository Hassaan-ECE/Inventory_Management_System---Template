"""Starter smoke tests for the ME inventory app and shared-first sync scheduling."""

from contextlib import ExitStack
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import QPoint, QEvent
from PySide6.QtWidgets import QApplication, QHeaderView, QMessageBox, QPushButton

from Code.db.database import create_tables, get_connection, insert_equipment
from Code.db.models import Equipment
from Code.gui.main_window import MainWindow, active_filter_specs
from Code.gui.equipment_table import DATA_COL_START, LINK_ROLE
from Code.sync.service import UpdateInfo


class MainWindowSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test.db"
        self.conn = get_connection(self.db_path)
        create_tables(self.conn)
        self._window_stacks: list[ExitStack] = []

    def tearDown(self) -> None:
        while self._window_stacks:
            self._window_stacks.pop().close()
        self.conn.close()
        self.temp_dir.cleanup()

    def _make_window(self) -> MainWindow:
        stack = ExitStack()
        stack.enter_context(patch("Code.gui.main_window.shared_sync_enabled", return_value=False))
        stack.enter_context(patch("Code.gui.main_window.update_checks_enabled", return_value=False))
        window = MainWindow(self.conn)
        self._window_stacks.append(stack)
        return window

    def _find_button(self, window: MainWindow, label_prefix: str) -> QPushButton | None:
        for button in window.findChildren(QPushButton):
            if button.text().strip().startswith(label_prefix):
                return button
        return None

    def test_window_can_be_created_against_empty_database(self) -> None:
        window = self._make_window()
        try:
            window.resize(1100, 700)
            window.show()
            self.app.processEvents()
            self.assertEqual(window.windowTitle(), "Inventory Management System")
            headers = [
                window.table.horizontalHeaderItem(index).text()
                for index in range(window.table.columnCount())
            ]
            self.assertEqual(
                headers,
                ["✓", "Asset #", "Qty", "Manufacturer", "Model", "Description", "Project", "Location", "Links"],
            )
            self.assertTrue(window.table.isColumnHidden(DATA_COL_START))
            self.assertTrue(window.table.isColumnHidden(headers.index("Project")))
            self.assertNotIn("Est. Age (Yrs)", headers)
            self.assertNotIn("Status", headers)
            self.assertNotIn("Calibration", headers)
            self.assertEqual(
                [field for _, field, _ in active_filter_specs()],
                ["asset_number", "manufacturer", "model", "description", "location"],
            )
            self.assertEqual(
                window.statusBar().currentMessage(),
                "Total: 0  |  Verified: 0/0  |  Import Issues: 0",
            )
            qty_index = headers.index("Qty")
            self.assertEqual(window.table.horizontalHeader().sectionViewportPosition(qty_index), 40)
        finally:
            window.close()

    def test_archive_tab_switches_between_inventory_and_archived_records(self) -> None:
        insert_equipment(
            self.conn,
            Equipment(
                asset_number="ME-300",
                manufacturer="Fixture Cart",
                description="Current fixture cart",
                location="Storage",
            ),
        )
        insert_equipment(
            self.conn,
            Equipment(
                asset_number="ME-301",
                manufacturer="Retired Cart",
                description="Old fixture cart",
                location="Archive",
                is_archived=True,
            ),
        )

        window = self._make_window()
        try:
            window.resize(1100, 700)
            window.show()
            self.app.processEvents()

            headers = [
                window.table.horizontalHeaderItem(index).text()
                for index in range(window.table.columnCount())
            ]
            manufacturer_index = headers.index("Manufacturer")

            self.assertEqual(window.view_tabs.tabText(0), "Inventory (1)")
            self.assertEqual(window.view_tabs.tabText(1), "Archive (1)")
            self.assertEqual(window.table.rowCount(), 1)
            self.assertEqual(window.table.item(0, manufacturer_index).text(), "Fixture Cart")

            window.view_tabs.setCurrentIndex(1)
            self.app.processEvents()

            self.assertEqual(window.table.rowCount(), 1)
            self.assertEqual(window.table.item(0, manufacturer_index).text(), "Retired Cart")
            self.assertEqual(window.results_label.text(), "Showing all 1 archived records")
        finally:
            window.close()

    def test_archive_action_moves_record_out_of_inventory_view(self) -> None:
        record_id = insert_equipment(
            self.conn,
            Equipment(
                asset_number="ME-302",
                manufacturer="Fixture Cart",
                description="Archivable cart",
                location="Storage",
            ),
        )

        window = self._make_window()
        try:
            window.resize(1100, 700)
            window.show()
            self.app.processEvents()

            with patch("Code.gui.main_window.QMessageBox.question", return_value=QMessageBox.Yes):
                window._set_row_archived(0, archived=True)
                self.app.processEvents()

            row = self.conn.execute(
                "SELECT is_archived FROM equipment WHERE record_id=?",
                (record_id,),
            ).fetchone()
            self.assertEqual(row["is_archived"], 1)
            self.assertEqual(window.table.rowCount(), 0)
            self.assertEqual(window.view_tabs.tabText(0), "Inventory (0)")
            self.assertEqual(window.view_tabs.tabText(1), "Archive (1)")

            window.view_tabs.setCurrentIndex(1)
            self.app.processEvents()
            self.assertEqual(window.table.rowCount(), 1)
        finally:
            window.close()

    def test_close_does_not_force_queue_flush_in_shared_first_mode(self) -> None:
        window = self._make_window()
        try:
            window.resize(1100, 700)
            window.show()
            self.app.processEvents()

            window._pending_sync_timer.setInterval(30000)
            window._pending_sync_timer.start()
            with patch.object(window, "_run_shared_sync") as run_sync:
                window.close()
                self.app.processEvents()

            run_sync.assert_not_called()
        finally:
            window.close()

    def test_activation_change_schedules_foreground_authoritative_sync(self) -> None:
        window = self._make_window()
        try:
            window.resize(1100, 700)
            window.show()
            self.app.processEvents()

            window._foreground_sync_timer.setInterval(0)
            with patch("Code.gui.main_window.shared_sync_enabled", new=lambda: True), patch.object(
                window, "isActiveWindow", return_value=True
            ), patch.object(window, "_run_shared_sync") as run_sync:
                window.changeEvent(QEvent(QEvent.ActivationChange))
                self.app.processEvents()

            run_sync.assert_called_once_with(quiet=True)
        finally:
            window.close()

    def test_shared_db_change_schedules_near_immediate_authoritative_sync(self) -> None:
        window = self._make_window()
        try:
            window.resize(1100, 700)
            window.show()
            self.app.processEvents()

            window._shared_change_sync_timer.setInterval(0)
            with patch("Code.gui.main_window.shared_sync_enabled", new=lambda: True), patch.object(
                window, "_refresh_shared_watch_paths"
            ), patch.object(window, "_run_shared_sync") as run_sync:
                window._on_shared_path_changed("S:/shared/me_lab_shared.db")
                self.app.processEvents()

            run_sync.assert_called_once_with(quiet=True)
        finally:
            window.close()

    def test_background_shared_sync_loss_does_not_show_modal_popup(self) -> None:
        window = self._make_window()
        try:
            window.resize(1100, 700)
            window.show()
            self.app.processEvents()

            with patch("Code.gui.main_window.QMessageBox.warning") as warning:
                window._on_sync_completed(
                    {"shared_available": False, "busy": False, "queued": 0, "pulled": 0, "flushed": 0, "superseded": 0}
                )
                self.app.processEvents()

            warning.assert_not_called()
            self.assertTrue(window._reconnect_timer.isActive())
        finally:
            window.close()

    def test_disconnected_state_disables_edit_and_import_actions(self) -> None:
        window = self._make_window()
        try:
            window.resize(1100, 700)
            window.show()
            self.app.processEvents()

            import_button = self._find_button(window, "Import Data")
            add_button = self._find_button(window, "+ Add")
            self.assertIsNotNone(import_button)
            self.assertIsNotNone(add_button)
            assert import_button is not None
            assert add_button is not None

            with patch("Code.gui.main_window.shared_sync_enabled", new=lambda: True):
                window._on_sync_completed({"shared_available": True, "busy": False, "queued": 0, "pulled": 0, "flushed": 0, "superseded": 0})
                self.app.processEvents()
                self.assertTrue(import_button.isEnabled())
                self.assertTrue(add_button.isEnabled())

                window._on_sync_completed({"shared_available": False, "busy": False, "queued": 0, "pulled": 0, "flushed": 0, "superseded": 0})
                self.app.processEvents()
                self.assertFalse(import_button.isEnabled())
                self.assertFalse(add_button.isEnabled())

            window._on_sync_completed({"shared_available": True, "busy": False, "queued": 0, "pulled": 0, "flushed": 0, "superseded": 0})
            self.app.processEvents()
            self.assertTrue(import_button.isEnabled())
            self.assertTrue(add_button.isEnabled())
        finally:
            window.close()

    def test_accepting_available_update_launches_installer_and_closes_app(self) -> None:
        window = self._make_window()
        try:
            window.resize(1100, 700)
            window.show()
            self.app.processEvents()

            installer_path = Path(self.temp_dir.name) / "ME_Lab_Inventory_Setup.exe"
            update_info = UpdateInfo(
                version="0.9.1",
                installer_path=installer_path,
                published_at="2026-04-17T10:04:22",
                notes="Internal bug-fix prerelease",
            )

            with patch("Code.gui.main_window.check_for_update", return_value=update_info), patch(
                "Code.gui.main_window.QMessageBox.question",
                return_value=QMessageBox.Yes,
            ), patch.object(window, "_launch_update_installer", return_value=True) as launch_installer, patch.object(
                window, "_quit_for_update"
            ) as quit_for_update:
                window._prompt_for_available_update()

            launch_installer.assert_called_once_with(installer_path)
            self.assertEqual(window.statusBar().currentMessage(), "Opened installer for version 0.9.1. Closing app for update.")
            quit_for_update.assert_called_once_with()
        finally:
            window.close()

    def test_qty_starts_at_minimum_width_and_other_me_columns_start_evenly(self) -> None:
        window = self._make_window()
        try:
            window.resize(1100, 700)
            window.show()
            self.app.processEvents()

            headers = [
                window.table.horizontalHeaderItem(index).text()
                for index in range(window.table.columnCount())
            ]
            qty_index = headers.index("Qty")
            other_indices = [headers.index(name) for name in ("Manufacturer", "Model", "Description", "Location", "Links")]
            other_widths = [window.table.columnWidth(index) for index in other_indices]

            self.assertEqual(
                window.table.columnWidth(qty_index),
                window.table._minimum_width_for_column(qty_index),
            )
            self.assertLessEqual(max(other_widths) - min(other_widths), 1)
        finally:
            window.close()

    def test_description_column_keeps_interactive_resize_handle(self) -> None:
        window = self._make_window()
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
        window = self._make_window()
        try:
            window.resize(1100, 700)
            window.show()
            self.app.processEvents()
            headers = [
                window.table.horizontalHeaderItem(index).text()
                for index in range(window.table.columnCount())
            ]
            last_visible_index = max(
                index
                for index in range(DATA_COL_START, window.table.columnCount())
                if not window.table.isColumnHidden(index)
            )
            self.assertEqual(headers[last_visible_index], "Links")
            self.assertEqual(
                window.table.horizontalHeader().sectionResizeMode(last_visible_index),
                QHeaderView.Fixed,
            )
        finally:
            window.close()

    def test_location_becomes_last_visible_column_when_links_is_hidden(self) -> None:
        window = self._make_window()
        try:
            window.resize(1100, 700)
            window.show()
            self.app.processEvents()
            headers = [
                window.table.horizontalHeaderItem(index).text()
                for index in range(window.table.columnCount())
            ]
            links_index = headers.index("Links")
            location_index = headers.index("Location")

            window._set_column_visible(links_index, False, 220)

            self.assertTrue(window.table.isColumnHidden(links_index))
            self.assertEqual(
                window.table.horizontalHeader().sectionResizeMode(location_index),
                QHeaderView.Fixed,
            )
            self.assertEqual(
                window.table.horizontalHeader().sectionResizeMode(headers.index("Description")),
                QHeaderView.Interactive,
            )
        finally:
            window.close()

    def test_non_last_column_resize_is_clamped_and_uses_title_based_minimum(self) -> None:
        window = self._make_window()
        try:
            window.resize(1100, 700)
            window.show()
            self.app.processEvents()

            headers = [
                window.table.horizontalHeaderItem(index).text()
                for index in range(window.table.columnCount())
            ]
            manufacturer_index = headers.index("Manufacturer")
            links_index = headers.index("Links")
            header = window.table.horizontalHeader()

            expected_min_width = max(
                header.minimumSectionSize(),
                header.fontMetrics().horizontalAdvance("Manufacturer") + 28,
            )
            self.assertEqual(
                window.table._minimum_width_for_column(manufacturer_index),
                expected_min_width,
            )

            window.table.setColumnWidth(manufacturer_index, 4000)
            self.app.processEvents()

            visible_width = sum(
                window.table.columnWidth(index)
                for index in range(window.table.columnCount())
                if not window.table.isColumnHidden(index)
            )
            self.assertLessEqual(visible_width, window.table.viewport().width() + 1)
            self.assertGreaterEqual(
                window.table.columnWidth(manufacturer_index),
                window.table._minimum_width_for_column(manufacturer_index),
            )
            self.assertGreaterEqual(
                window.table.columnWidth(links_index),
                window.table._minimum_width_for_column(links_index),
            )
        finally:
            window.close()

    def test_short_header_columns_can_use_smaller_minimum_widths(self) -> None:
        window = self._make_window()
        try:
            window.resize(1100, 700)
            window.show()
            self.app.processEvents()

            headers = [
                window.table.horizontalHeaderItem(index).text()
                for index in range(window.table.columnCount())
            ]
            qty_index = headers.index("Qty")
            header = window.table.horizontalHeader()
            expected_qty_min = max(
                header.minimumSectionSize(),
                header.fontMetrics().horizontalAdvance("Qty") + 28,
            )

            self.assertEqual(window.table._minimum_width_for_column(qty_index), expected_qty_min)
            self.assertLess(window.table._minimum_width_for_column(qty_index), 72)
        finally:
            window.close()

    def test_hidden_asset_column_moves_out_of_the_left_edge(self) -> None:
        window = self._make_window()
        try:
            window.resize(1100, 700)
            window.show()
            self.app.processEvents()

            headers = [
                window.table.horizontalHeaderItem(index).text()
                for index in range(window.table.columnCount())
            ]
            asset_index = headers.index("Asset #")
            qty_index = headers.index("Qty")
            header = window.table.horizontalHeader()

            self.assertTrue(window.table.isColumnHidden(asset_index))
            self.assertGreater(header.visualIndex(asset_index), header.visualIndex(qty_index))
            self.assertEqual(header.sectionViewportPosition(qty_index), 40)
        finally:
            window.close()

    def test_verified_column_can_be_hidden(self) -> None:
        window = self._make_window()
        try:
            window.resize(1100, 700)
            window.show()
            self.app.processEvents()

            headers = [
                window.table.horizontalHeaderItem(index).text()
                for index in range(window.table.columnCount())
            ]
            qty_index = headers.index("Qty")

            window._set_column_visible(0, False, 40)
            self.app.processEvents()

            self.assertTrue(window.table.isColumnHidden(0))
            self.assertEqual(window.table.horizontalHeader().sectionViewportPosition(qty_index), 0)
        finally:
            window.close()

    def test_last_data_column_stays_visible_even_if_verified_is_shown(self) -> None:
        window = self._make_window()
        try:
            window.resize(1100, 700)
            window.show()
            self.app.processEvents()

            headers = [
                window.table.horizontalHeaderItem(index).text()
                for index in range(window.table.columnCount())
            ]
            visible_data_indices = [
                index
                for index in range(DATA_COL_START, window.table.columnCount())
                if not window.table.isColumnHidden(index)
            ]
            last_data_index = visible_data_indices[-1]

            for index in visible_data_indices[:-1]:
                window._set_column_visible(index, False, window.table.columnWidth(index))

            self.app.processEvents()
            self.assertFalse(window.table.isColumnHidden(0))

            window._set_column_visible(last_data_index, False, window.table.columnWidth(last_data_index))
            self.app.processEvents()

            self.assertFalse(window.table.isColumnHidden(last_data_index))
            self.assertEqual(headers[last_data_index], "Links")
        finally:
            window.close()

    def test_last_visible_column_keeps_minimum_width(self) -> None:
        window = self._make_window()
        try:
            window.resize(1100, 700)
            window.show()
            self.app.processEvents()

            headers = [
                window.table.horizontalHeaderItem(index).text()
                for index in range(window.table.columnCount())
            ]
            location_index = headers.index("Location")
            links_index = headers.index("Links")

            window.table.setColumnWidth(location_index, 0)
            window.table.setColumnWidth(links_index, 0)
            self.app.processEvents()

            self.assertGreaterEqual(
                window.table.columnWidth(location_index),
                window.table._minimum_width_for_column(location_index),
            )
            self.assertGreaterEqual(
                window.table.columnWidth(links_index),
                window.table._minimum_width_for_column(links_index),
            )
        finally:
            window.close()

    def test_links_cell_shows_hover_hint_and_opens_saved_url(self) -> None:
        insert_equipment(
            self.conn,
            Equipment(
                asset_number="ME-200",
                manufacturer="Fixture Co",
                description="Fixture cart",
                location="Storage",
                links="https://vendor.example/fixture-cart",
            ),
        )

        window = self._make_window()
        try:
            window.resize(1100, 700)
            window.show()
            self.app.processEvents()

            headers = [
                window.table.horizontalHeaderItem(index).text()
                for index in range(window.table.columnCount())
            ]
            links_index = headers.index("Links")
            links_item = window.table.item(0, links_index)

            self.assertIsNotNone(links_item)
            self.assertEqual(links_item.text(), "vendor.example/fixture-cart")
            self.assertEqual(links_item.data(LINK_ROLE), "https://vendor.example/fixture-cart")

            with patch("Code.gui.main_window.QDesktopServices.openUrl", return_value=True) as open_url:
                window._open_record_link(0)

            open_url.assert_called_once()
            self.assertEqual(
                open_url.call_args.args[0].toString(),
                "https://vendor.example/fixture-cart",
            )
        finally:
            window.close()

    def test_links_column_shows_shortened_display_for_long_urls(self) -> None:
        insert_equipment(
            self.conn,
            Equipment(
                asset_number="ME-201",
                manufacturer="CEJN",
                description="QD coupling",
                location="Storage",
                links=(
                    "https://www.cejn.com/en-us/products/thermal-control/"
                    "?filters=null%3D1191&mtm_campaign=Semicon-Campaign&mtm_content="
                    "Semicon-Ad-Group-2&mtm_kwd=universal+quick+disconnect+couplings"
                ),
            ),
        )

        window = self._make_window()
        try:
            window.resize(1100, 700)
            window.show()
            self.app.processEvents()

            headers = [
                window.table.horizontalHeaderItem(index).text()
                for index in range(window.table.columnCount())
            ]
            links_index = headers.index("Links")
            links_item = window.table.item(0, links_index)

            self.assertIsNotNone(links_item)
            self.assertEqual(
                links_item.text(),
                "www.cejn.com/en-us/products/thermal-control",
            )
            self.assertEqual(
                links_item.data(LINK_ROLE),
                (
                    "https://www.cejn.com/en-us/products/thermal-control/"
                    "?filters=null%3D1191&mtm_campaign=Semicon-Campaign&mtm_content="
                    "Semicon-Ad-Group-2&mtm_kwd=universal+quick+disconnect+couplings"
                ),
            )
        finally:
            window.close()

    def test_links_hover_hint_uses_short_ctrl_click_text(self) -> None:
        insert_equipment(
            self.conn,
            Equipment(
                asset_number="ME-202",
                manufacturer="CEJN",
                description="QD coupling",
                location="Storage",
                links="https://vendor.example/fixture-cart",
            ),
        )

        window = self._make_window()
        try:
            window.resize(1100, 700)
            window.show()
            self.app.processEvents()

            headers = [
                window.table.horizontalHeaderItem(index).text()
                for index in range(window.table.columnCount())
            ]
            links_index = headers.index("Links")
            link_rect = window.table.visualItemRect(window.table.item(0, links_index))

            with patch("Code.gui.main_window.QToolTip.showText") as show_text:
                window._show_link_hover_hint(link_rect.center())

            show_text.assert_called_once()
            self.assertEqual(show_text.call_args.args[1], "Ctrl+Click to open")
        finally:
            window.close()


if __name__ == "__main__":
    unittest.main()

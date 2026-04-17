"""Single-page search-driven equipment lookup."""

import subprocess
import sqlite3
import tempfile
import urllib.parse
from pathlib import Path

from PySide6.QtCore import QEvent, QFileSystemWatcher, QPoint, Qt, QTimer, QUrl
from PySide6.QtGui import QDesktopServices, QGuiApplication
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QStatusBar,
    QTabBar,
    QToolTip,
    QVBoxLayout,
    QWidget,
)

from app_config import APP_CONFIG
from Code.db.database import (
    delete_equipment,
    get_distinct_equipment_values,
    import_database_snapshot,
    get_equipment_by_id,
    get_equipment_stats,
    search_equipment,
    update_equipment,
)
from Code.db.models import Equipment
from Code.gui.equipment_table import (
    active_columns,
    DATA_COL_START,
    LINK_ROLE,
    VERIFY_COL,
    EquipmentTable,
    format_table_value,
    verified_color,
)
from Code.gui.theme import (
    DEFAULT_THEME_NAME,
    get_stylesheet,
    normalize_theme_name,
)
from Code.gui.quick_edit_dialog import QuickEditDialog
from Code.gui.search_helpers import build_age_search_query, build_search_query
from Code.gui.ui_components import CardWidget
from Code.gui.window_branding import apply_window_branding
from Code.importer.normalizer import normalize_manufacturer
from Code.sync.service import (
    check_for_update,
    shared_sync_enabled,
    sync_interval_ms,
    sync_local_with_shared,
    update_checks_enabled,
)
from Code.utils.equipment_fields import parse_age_years
from Code.utils.runtime_paths import (
    bundle_root,
    executable_dir,
    is_compiled,
    resolve_data_dir,
    shared_database_dir,
    shared_db_path,
)

_SEARCH_URL_TEMPLATE = "https://www.google.com/search?q={query}"
QUICK_EDIT_OPTIONS = {
    "lifecycle_status": ["active", "repair", "scrapped", "missing", "rental"],
    "working_status": ["working", "limited", "not_working", "unknown"],
    "calibration_status": ["calibrated", "reference_only", "out_to_cal", "unknown"],
}
QUICK_EDIT_SUGGEST_FIELDS = {"manufacturer", "model", "description", "location"}
ALL_FILTER_SPECS = [
    ("Asset #", "asset_number", "text"),
    ("Quantity", "qty", "text"),
    ("Manufacturer", "manufacturer", "text"),
    ("Model", "model", "text"),
    ("Description", "description", "text"),
    ("Est. Age (Yrs)", "estimated_age_years", "text"),
    ("Status", "lifecycle_status", "combo"),
    ("Working", "working_status", "combo"),
    ("Calibration", "calibration_status", "combo"),
    ("Location", "location", "text"),
]
ACTIVE_RECORD_SCOPE = "active"
ARCHIVED_RECORD_SCOPE = "archived"


class MainWindow(QMainWindow):
    """One-page, search-first equipment lookup window."""

    def __init__(self, conn: sqlite3.Connection, initial_theme_name: str = DEFAULT_THEME_NAME, parent=None):
        super().__init__(parent)
        self.conn = conn
        self._theme_name = normalize_theme_name(initial_theme_name)
        self._columns = active_columns()
        self._column_widths = {index + DATA_COL_START: width for index, (_, _, width) in enumerate(self._columns)}
        self._record_scope = ACTIVE_RECORD_SCOPE

        apply_window_branding(self)
        self._apply_initial_window_size()

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(250)
        self._timer.timeout.connect(self._do_search)
        self._hovered_link_cell: tuple[int, int] | None = None
        self._pending_sync_timer = QTimer(self)
        self._pending_sync_timer.setSingleShot(True)
        self._pending_sync_timer.setInterval(0)
        self._pending_sync_timer.timeout.connect(lambda: self._run_shared_sync(quiet=True))
        self._foreground_sync_timer = QTimer(self)
        self._foreground_sync_timer.setSingleShot(True)
        self._foreground_sync_timer.setInterval(1000)
        self._foreground_sync_timer.timeout.connect(lambda: self._run_shared_sync(quiet=True))
        self._shared_change_sync_timer = QTimer(self)
        self._shared_change_sync_timer.setSingleShot(True)
        self._shared_change_sync_timer.setInterval(0)
        self._shared_change_sync_timer.timeout.connect(lambda: self._run_shared_sync(quiet=True))
        self._periodic_sync_timer = QTimer(self)
        self._periodic_sync_timer.setInterval(sync_interval_ms())
        self._periodic_sync_timer.timeout.connect(lambda: self._run_shared_sync(quiet=True))
        self._shared_watcher = QFileSystemWatcher(self)
        self._shared_watcher.fileChanged.connect(self._on_shared_path_changed)
        self._shared_watcher.directoryChanged.connect(self._on_shared_path_changed)
        self._update_prompted_version = ""

        self._setup_ui()
        self._do_search()
        if shared_sync_enabled():
            self._refresh_shared_watch_paths()
            self._periodic_sync_timer.start()
        if shared_sync_enabled() or (update_checks_enabled() and is_compiled()):
            QTimer.singleShot(1200, self._run_startup_maintenance)

    def _apply_initial_window_size(self) -> None:
        """Size the main window to the current display instead of assuming a large monitor."""
        min_width = 960
        min_height = 640
        self.setMinimumSize(min_width, min_height)

        screen = QGuiApplication.primaryScreen()
        if screen is None:
            self.resize(1280, 800)
            return

        available = screen.availableGeometry()
        compact_display = available.width() <= 1920 or available.height() <= 1080

        target_width = 1220 if compact_display else 1360
        target_height = 760 if compact_display else 860

        width = min(target_width, max(min_width, available.width() - 120))
        height = min(target_height, max(min_height, available.height() - 120))
        self.resize(width, height)

    def _setup_ui(self) -> None:
        record_label = getattr(APP_CONFIG, "record_label", "Record").strip() or "Record"

        central = QWidget()
        self.setCentralWidget(central)

        root = QVBoxLayout(central)
        root.setContentsMargins(20, 20, 20, 12)
        root.setSpacing(14)

        header = QHBoxLayout()
        header.setSpacing(12)

        title = QLabel(APP_CONFIG.display_name)
        title.setObjectName("pageTitle")
        header.addWidget(title)
        header.addStretch()

        self.view_tabs = QTabBar()
        self.view_tabs.setDocumentMode(True)
        self.view_tabs.setDrawBase(False)
        self.view_tabs.setExpanding(False)
        self.view_tabs.addTab("Inventory")
        self.view_tabs.addTab("Archive")
        self.view_tabs.currentChanged.connect(self._on_view_tab_changed)
        header.addWidget(self.view_tabs)

        self.theme_toggle_btn = QPushButton()
        self.theme_toggle_btn.setObjectName("secondaryButton")
        self.theme_toggle_btn.setMinimumWidth(132)
        self.theme_toggle_btn.clicked.connect(self._toggle_theme)
        header.addWidget(self.theme_toggle_btn)

        import_btn = QPushButton("Import Data")
        import_btn.setObjectName("secondaryButton")
        import_btn.setToolTip("Merge from the Excel files or copy data from a shared .db file")
        import_btn.clicked.connect(self._on_import_data)
        header.addWidget(import_btn)

        export_btn = QPushButton("Export Excel")
        export_btn.setObjectName("secondaryButton")
        export_btn.setToolTip("Export all equipment data to a clean Excel file")
        export_btn.clicked.connect(self._on_export)
        header.addWidget(export_btn)

        export_html_btn = QPushButton("Export HTML")
        export_html_btn.setObjectName("secondaryButton")
        export_html_btn.setToolTip("Export a standalone verified-equipment HTML report")
        export_html_btn.clicked.connect(self._on_export_html)
        header.addWidget(export_html_btn)

        add_btn = QPushButton(f"+ Add {record_label}")
        add_btn.setObjectName("primaryButton")
        add_btn.clicked.connect(self._on_add)
        header.addWidget(add_btn)

        self._update_theme_toggle_button()
        root.addLayout(header)

        search_card = CardWidget("heroCard")
        search_layout = QVBoxLayout(search_card)
        search_layout.setContentsMargins(24, 20, 24, 20)
        search_layout.setSpacing(10)

        self.search_input = QLineEdit()
        self._update_search_placeholder()
        self.search_input.setStyleSheet("font-size: 16px; padding: 14px 18px; border-radius: 12px;")
        self.search_input.textChanged.connect(lambda: self._timer.start())
        self.search_input.returnPressed.connect(self._do_search)
        search_layout.addWidget(self.search_input)

        results_row = QHBoxLayout()
        results_row.setSpacing(10)

        self.results_label = QLabel("")
        self.results_label.setObjectName("pageSubtitle")
        results_row.addWidget(self.results_label, 1)

        self.color_rows_checkbox = QCheckBox("Color Rows")
        self.color_rows_checkbox.setChecked(True)
        self.color_rows_checkbox.stateChanged.connect(lambda _: self._do_search())
        results_row.addWidget(self.color_rows_checkbox)

        self.filter_toggle_btn = QPushButton("Filters")
        self.filter_toggle_btn.setObjectName("secondaryButton")
        self.filter_toggle_btn.setCheckable(True)
        self.filter_toggle_btn.clicked.connect(self._toggle_filters_panel)
        results_row.addWidget(self.filter_toggle_btn)

        search_layout.addLayout(results_row)

        root.addWidget(search_card)

        self.filter_card = CardWidget("toolbarCard")
        filter_layout = QVBoxLayout(self.filter_card)
        filter_layout.setContentsMargins(18, 16, 18, 16)
        filter_layout.setSpacing(10)

        filter_title = QLabel("Column Filters")
        filter_title.setObjectName("sectionHeader")
        filter_layout.addWidget(filter_title)

        filters_grid = QGridLayout()
        filters_grid.setHorizontalSpacing(10)
        filters_grid.setVerticalSpacing(10)

        self.column_filters: dict[str, QLineEdit | QComboBox] = {}

        filter_specs = active_filter_specs()

        combo_values = {
            "lifecycle_status": ["", "active", "repair", "scrapped", "missing", "rental"],
            "working_status": ["", "working", "limited", "not_working", "unknown"],
            "calibration_status": ["", "calibrated", "reference_only", "out_to_cal", "unknown"],
        }

        for index, (label_text, field, filter_type) in enumerate(filter_specs):
            row = (index // 4) * 2
            column = index % 4

            label = QLabel(label_text)
            label.setObjectName("sectionSubheader")
            filters_grid.addWidget(label, row, column)

            if filter_type == "combo":
                widget = QComboBox()
                widget.addItem(f"All {label_text}")
                for value in combo_values[field][1:]:
                    widget.addItem(value)
                widget.currentIndexChanged.connect(self._schedule_search)
            else:
                widget = QLineEdit()
                widget.setPlaceholderText(f"Filter {label_text.lower()}")
                widget.textChanged.connect(self._schedule_search)

            self.column_filters[field] = widget
            filters_grid.addWidget(widget, row + 1, column)

        filter_layout.addLayout(filters_grid)

        filter_actions = QHBoxLayout()
        filter_actions.addStretch()

        clear_filters_btn = QPushButton("Clear Column Filters")
        clear_filters_btn.setObjectName("secondaryButton")
        clear_filters_btn.clicked.connect(self._clear_column_filters)
        filter_actions.addWidget(clear_filters_btn)

        filter_layout.addLayout(filter_actions)
        self.filter_card.hide()
        root.addWidget(self.filter_card)

        table_card = CardWidget("panelCard")
        table_layout = QVBoxLayout(table_card)
        table_layout.setContentsMargins(14, 14, 14, 14)
        table_layout.setSpacing(0)

        self.table = EquipmentTable(self._theme_name)
        self.table.setMouseTracking(True)

        header_view = self.table.horizontalHeader()
        header_view.setContextMenuPolicy(Qt.CustomContextMenu)
        header_view.customContextMenuRequested.connect(self._show_header_menu)

        self.table.viewport().setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.viewport().setMouseTracking(True)
        self.table.viewport().customContextMenuRequested.connect(self._show_cell_menu)
        self.table.viewport().installEventFilter(self)
        self.table.cellClicked.connect(self._on_cell_clicked)
        self.table.itemDoubleClicked.connect(lambda _: self._on_edit())

        table_layout.addWidget(self.table, 1)
        root.addWidget(table_card, 1)

        self.not_found_row = QHBoxLayout()
        self.not_found_label = QLabel("Can't find what you're looking for?")
        self.not_found_label.setObjectName("sectionSubheader")
        self.not_found_row.addWidget(self.not_found_label)

        not_found_btn = QPushButton(f"Add {record_label}")
        not_found_btn.setObjectName("primaryButton")
        not_found_btn.clicked.connect(self._on_add)
        self.not_found_row.addWidget(not_found_btn)
        self.not_found_row.addStretch()

        self.not_found_widget = QWidget()
        self.not_found_widget.setLayout(self.not_found_row)
        self.not_found_widget.hide()
        root.addWidget(self.not_found_widget)

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self._update_status_bar()

    def eventFilter(self, watched, event):
        """Force a reliable context menu for table cells on right-click."""
        if watched is self.table.viewport():
            if event.type() == QEvent.ContextMenu:
                self._show_cell_menu(event.pos())
                return True
            if event.type() == QEvent.MouseMove:
                self._show_link_hover_hint(event.pos())
            elif event.type() in {QEvent.Leave, QEvent.HoverLeave}:
                self._clear_link_hover_hint()
        return super().eventFilter(watched, event)

    def changeEvent(self, event) -> None:
        """Pull shared changes again when the window becomes active."""
        if event.type() == QEvent.ActivationChange and self.isActiveWindow():
            self._schedule_foreground_sync()
        super().changeEvent(event)

    def closeEvent(self, event) -> None:
        """Flush a pending local sync before the window closes."""
        if shared_sync_enabled():
            self._foreground_sync_timer.stop()
            self._shared_change_sync_timer.stop()
            if self._pending_sync_timer.isActive():
                self._pending_sync_timer.stop()
                self._run_shared_sync(quiet=True)
        super().closeEvent(event)

    def _schedule_search(self) -> None:
        """Debounce search/filter changes."""
        self._timer.start()

    def _toggle_theme(self) -> None:
        """Switch between the light and dark application themes."""
        next_theme = "dark" if self._theme_name == "light" else "light"
        self._apply_theme(next_theme)

    def _apply_theme(self, theme_name: str) -> None:
        """Apply the requested theme to the whole application."""
        self._theme_name = normalize_theme_name(theme_name)

        app = QApplication.instance()
        if app is not None:
            app.setStyleSheet(get_stylesheet(self._theme_name))

        self._update_theme_toggle_button()
        self._do_search()

    def _update_theme_toggle_button(self) -> None:
        """Update the top-right toggle label to match the current theme."""
        if self._theme_name == "light":
            self.theme_toggle_btn.setText("Switch to Dark")
            self.theme_toggle_btn.setToolTip("Use the dark application theme")
        else:
            self.theme_toggle_btn.setText("Switch to Light")
            self.theme_toggle_btn.setToolTip("Use the light application theme")

    def _toggle_filters_panel(self, checked: bool) -> None:
        """Show or hide the column filter panel."""
        self.filter_card.setVisible(checked)
        self.filter_toggle_btn.setText("Hide Filters" if checked else "Filters")

    def _on_view_tab_changed(self, index: int) -> None:
        """Switch between the main inventory view and the archive view."""
        self._record_scope = ARCHIVED_RECORD_SCOPE if index == 1 else ACTIVE_RECORD_SCOPE
        if not hasattr(self, "search_input"):
            return
        self._update_search_placeholder()
        self._do_search()

    def _is_archive_view(self) -> bool:
        """Return whether the archive view is currently selected."""
        return self._record_scope == ARCHIVED_RECORD_SCOPE

    def _update_search_placeholder(self) -> None:
        """Update the search prompt to match the current record scope."""
        if self._is_archive_view():
            text = 'Search archived records — manufacturer, model, description, location, or notes'
        else:
            text = 'Search equipment — type anything: model, serial, manufacturer, location, "scrapped", "calibrated"...'
        if hasattr(self, "search_input"):
            self.search_input.setPlaceholderText(text)

    def _refresh_view_tabs(self) -> None:
        """Show the current inventory/archive counts on the top view tabs."""
        stats = get_equipment_stats(self.conn)
        archived_count = stats.get("archived", 0)
        inventory_count = max(0, stats.get("total", 0) - archived_count)
        self.view_tabs.setTabText(0, f"Inventory ({inventory_count})")
        self.view_tabs.setTabText(1, f"Archive ({archived_count})")

    def _run_startup_maintenance(self) -> None:
        """Run lightweight startup tasks after the window is visible."""
        if shared_sync_enabled():
            self._run_shared_sync(quiet=True)
        if update_checks_enabled() and is_compiled():
            self._prompt_for_available_update()

    def _prompt_for_available_update(self) -> None:
        """Offer the published installer when a newer app version is available."""
        update_info = check_for_update()
        if update_info is None or update_info.version == self._update_prompted_version:
            return

        self._update_prompted_version = update_info.version
        published_suffix = f"\nPublished: {update_info.published_at}" if update_info.published_at else ""
        notes_suffix = f"\n\nNotes:\n{update_info.notes}" if update_info.notes else ""
        reply = QMessageBox.question(
            self,
            "Update Available",
            f"Version {update_info.version} is available for {APP_CONFIG.display_name}.{published_suffix}\n\n"
            "Open the installer now? The app will close so the update can finish cleanly."
            f"{notes_suffix}",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        )
        if reply != QMessageBox.Yes:
            return

        if not self._launch_update_installer(update_info.installer_path):
            QMessageBox.warning(
                self,
                "Update Available",
                f"Could not open the installer:\n{update_info.installer_path}",
            )
            return

        self.status_bar.showMessage(f"Opened installer for version {update_info.version}. Closing app for update.", 5000)
        self._quit_for_update()

    def _launch_update_installer(self, installer_path: Path) -> bool:
        """Start the published installer as a real child process."""
        try:
            subprocess.Popen(
                [str(installer_path)],
                cwd=str(installer_path.parent),
            )
        except OSError:
            return False
        return True

    def _quit_for_update(self) -> None:
        """Exit the running app after handing off to the installer."""
        self.hide()
        app = QApplication.instance()
        if app is None:
            return
        QTimer.singleShot(0, app.quit)

    def _schedule_shared_sync(self) -> None:
        """Queue a background sync after local changes settle."""
        if not shared_sync_enabled():
            return
        self._pending_sync_timer.start()

    def _schedule_foreground_sync(self) -> None:
        """Pull shared changes shortly after the window becomes active again."""
        if not shared_sync_enabled():
            return
        if self._pending_sync_timer.isActive():
            return
        self._foreground_sync_timer.start()

    def _refresh_shared_watch_paths(self) -> None:
        """Keep a live watch on the shared DB file and directory when available."""
        if not shared_sync_enabled():
            return

        desired_paths: list[str] = []
        shared_dir = shared_database_dir(create=False)
        if shared_dir is not None and shared_dir.exists():
            desired_paths.append(str(shared_dir))

        shared_path = shared_db_path()
        if shared_path is not None and shared_path.exists():
            desired_paths.append(str(shared_path))

        current_paths = set(self._shared_watcher.files()) | set(self._shared_watcher.directories())
        desired_set = set(desired_paths)

        for path in current_paths - desired_set:
            self._shared_watcher.removePath(path)

        for path in desired_set - current_paths:
            self._shared_watcher.addPath(path)

    def _on_shared_path_changed(self, _path: str) -> None:
        """React to shared DB file changes with a near-immediate pull."""
        self._refresh_shared_watch_paths()
        self._schedule_remote_sync()

    def _schedule_remote_sync(self) -> None:
        """Queue a very short debounce for a shared DB change notification."""
        if not shared_sync_enabled():
            return
        if self._pending_sync_timer.isActive():
            return
        self._shared_change_sync_timer.start()

    def _run_shared_sync(self, quiet: bool = False) -> None:
        """Synchronize the local database with the shared workspace."""
        if not shared_sync_enabled():
            return

        try:
            result = sync_local_with_shared(self.conn)
        except Exception as exc:
            if quiet:
                self.status_bar.showMessage(f"Shared sync skipped: {exc}", 5000)
            else:
                QMessageBox.warning(self, "Shared Sync", f"Shared sync failed:\n{exc}")
            return

        if result.pulled or result.initialized == "local":
            self._do_search()
            self._update_status_bar()
        elif result.pushed:
            self._refresh_view_tabs()
            self._update_status_bar()

        self._refresh_shared_watch_paths()

        if result.conflicts:
            self.status_bar.showMessage(result.message or "Shared sync found conflicts to review.", 7000)
            return

        if not quiet and result.message:
            self.status_bar.showMessage(result.message, 5000)
        elif quiet and (result.pulled or result.pushed or result.initialized):
            self.status_bar.showMessage(result.message, 5000)

    def _do_search(self) -> None:
        """Run the search query and populate the results table."""
        query = self.search_input.text().strip()
        filters = self._current_column_filter_values()
        results = search_equipment(
            self.conn,
            query,
            lifecycle=filters.get("lifecycle_status", ""),
            calibration=filters.get("calibration_status", ""),
            working=filters.get("working_status", ""),
            location=filters.get("location", ""),
            asset_number=filters.get("asset_number", ""),
            manufacturer=filters.get("manufacturer", ""),
            model=filters.get("model", ""),
            description=filters.get("description", ""),
            estimated_age_years=filters.get("estimated_age_years", ""),
            archived=self._record_scope,
        )
        self.table.set_theme_name(self._theme_name)
        self.table.set_color_rows_enabled(self.color_rows_checkbox.isChecked())
        self.table.populate(results)
        self._refresh_view_tabs()

        count = len(results)
        has_filters = self._has_active_column_filters()
        record_label = "archived records" if self._is_archive_view() else "equipment records"
        if not query:
            if self._is_archive_view() and count == 0 and not has_filters:
                self.results_label.setText("No archived records yet")
            elif has_filters:
                self.results_label.setText(f"Showing {count} filtered {record_label}")
            else:
                self.results_label.setText(f"Showing all {count} {record_label}")
            self.not_found_widget.hide()
        elif count > 0:
            suffix = " after column filters" if has_filters else ""
            if self._is_archive_view():
                self.results_label.setText(
                    f'{count} archived result{"s" if count != 1 else ""} for "{query}"{suffix}'
                )
            else:
                self.results_label.setText(f'{count} result{"s" if count != 1 else ""} for "{query}"{suffix}')
            self.not_found_widget.hide()
        else:
            if self._is_archive_view():
                self.results_label.setText(f'No archived results for "{query}"')
                self.not_found_widget.hide()
            else:
                self.results_label.setText(f'No results for "{query}"')
                self.not_found_widget.show()

    def _current_column_filter_values(self) -> dict[str, str]:
        """Return current per-column filter values in a DB-friendly shape."""
        values: dict[str, str] = {}
        for field, widget in self.column_filters.items():
            if isinstance(widget, QComboBox):
                value = widget.currentText().strip()
                values[field] = "" if value.startswith("All ") else value
            else:
                values[field] = widget.text().strip()
        return values

    def _has_active_column_filters(self) -> bool:
        """Return whether any column filter currently has a value."""
        return any(self._current_column_filter_values().values())

    def _clear_column_filters(self) -> None:
        """Reset all per-column filter widgets."""
        for widget in self.column_filters.values():
            if isinstance(widget, QComboBox):
                widget.setCurrentIndex(0)
            else:
                widget.clear()
        self._do_search()

    def _show_header_menu(self, position: QPoint) -> None:
        """Show a context menu for toggling visible table columns."""
        header = self.table.horizontalHeader()
        menu = QMenu(self)

        visible_data_count = sum(
            1 for col_idx in range(DATA_COL_START, self.table.columnCount())
            if not self.table.isColumnHidden(col_idx)
        )
        visible_verify = not self.table.isColumnHidden(VERIFY_COL)

        verify_action = menu.addAction("Verified")
        verify_action.setCheckable(True)
        verify_action.setChecked(visible_verify)
        verify_action.toggled.connect(
            lambda checked: self._set_column_visible(VERIFY_COL, checked, self.table.columnWidth(VERIFY_COL))
        )
        menu.addSeparator()

        for col_offset, (label, _, default_width) in enumerate(self._columns):
            table_col = col_offset + DATA_COL_START
            action = menu.addAction(label)
            action.setCheckable(True)
            is_visible = not self.table.isColumnHidden(table_col)
            action.setChecked(is_visible)
            if is_visible and visible_data_count == 1:
                action.setEnabled(False)
            action.toggled.connect(
                lambda checked, idx=table_col, width=default_width: self._set_column_visible(idx, checked, width)
            )

        menu.exec(header.mapToGlobal(position))

    def _set_column_visible(self, column_index: int, visible: bool, default_width: int) -> None:
        """Toggle a table column while preserving at least one visible data column."""
        currently_visible = not self.table.isColumnHidden(column_index)
        if currently_visible == visible:
            return

        visible_data_columns = [
            index for index in range(DATA_COL_START, self.table.columnCount())
            if not self.table.isColumnHidden(index)
        ]
        if column_index >= DATA_COL_START and not visible and len(visible_data_columns) == 1:
            return

        visible_columns = [
            index for index in range(self.table.columnCount())
            if not self.table.isColumnHidden(index)
        ]
        if not visible and len(visible_columns) == 1:
            return

        if not visible:
            self._column_widths[column_index] = self.table.columnWidth(column_index)
            self.table.setColumnHidden(column_index, True)
            return

        self.table.setColumnHidden(column_index, False)
        self.table.setColumnWidth(column_index, self._column_widths.get(column_index, default_width))

    def _show_cell_menu(self, position: QPoint) -> None:
        """Show a context menu for search and quick row actions."""
        item = self.table.itemAt(position)
        if item is None:
            return

        self.table.setCurrentCell(item.row(), item.column())

        column_index = item.column()
        menu = QMenu(self)

        quick_edit_action = None
        if column_index >= DATA_COL_START:
            label, _, _ = self._columns[column_index - DATA_COL_START]
            quick_edit_action = menu.addAction(f"Edit {label}")

        open_record_action = menu.addAction("Open Full Record")
        archive_action = menu.addAction("Restore Record" if self._is_archive_view() else "Archive Record")
        menu.addSeparator()
        search_online_action = menu.addAction("Search Online")
        search_year_action = None
        copy_info_action = None
        if _show_age_search_actions():
            search_year_action = menu.addAction("Search Equipment Age")
            copy_info_action = menu.addAction("Copy Age Search")
        menu.addSeparator()
        delete_action = menu.addAction("Delete Record")

        chosen_action = menu.exec(self.table.viewport().mapToGlobal(position))
        if chosen_action is None:
            return
        if chosen_action == quick_edit_action and column_index >= DATA_COL_START:
            self._quick_edit_cell(item.row(), column_index)
        elif chosen_action == open_record_action:
            self._on_edit()
        elif chosen_action == archive_action:
            self._set_row_archived(item.row(), archived=not self._is_archive_view())
        elif chosen_action == search_online_action:
            self._search_equipment_online(item.row())
        elif search_year_action is not None and chosen_action == search_year_action:
            self._search_equipment_online(item.row(), mode="year")
        elif copy_info_action is not None and chosen_action == copy_info_action:
            self._copy_equipment_info(item.row())
        elif chosen_action == delete_action:
            self._on_delete()

    def _quick_edit_cell(self, row: int, column_index: int) -> None:
        """Edit a single visible field using a field-aware prompt."""
        record_id = self.table.record_id_for_row(row)
        if record_id is None:
            return
        eq = get_equipment_by_id(self.conn, record_id)
        if eq is None:
            return

        label, field, _ = self._columns[column_index - DATA_COL_START]
        current_raw_value = getattr(eq, field, "")
        current_value = self._format_table_value(field, "" if current_raw_value is None else current_raw_value)

        if field in QUICK_EDIT_OPTIONS:
            dialog = QuickEditDialog(
                label=label,
                current_value=current_value,
                options=QUICK_EDIT_OPTIONS[field],
                parent=self,
            )
        else:
            suggestions = []
            if field in QUICK_EDIT_SUGGEST_FIELDS:
                suggestions = get_distinct_equipment_values(self.conn, field)

            dialog = QuickEditDialog(
                label=label,
                current_value=current_value,
                suggestions=suggestions,
                parent=self,
            )

        if dialog.exec() != QDialog.Accepted:
            return

        new_value = dialog.value().strip()
        if new_value == current_value:
            return

        if field == "manufacturer":
            eq.manufacturer_raw = new_value
            eq.manufacturer = normalize_manufacturer(new_value)
        elif field == "qty":
            if not new_value:
                eq.qty = None
            else:
                try:
                    eq.qty = float(new_value)
                except ValueError:
                    QMessageBox.warning(
                        self,
                        "Invalid Quantity",
                        "Enter quantity as a number, for example 4 or 4.5.",
                    )
                    return
        elif field == "estimated_age_years":
            age_value = parse_age_years(new_value)
            if new_value and age_value is None:
                QMessageBox.warning(
                    self,
                    "Invalid Age",
                    "Enter age in years as a number, for example 10 or 10.5.",
                )
                return

            eq.estimated_age_years = age_value
            if age_value is None:
                eq.age_basis = "unknown"
            elif age_value != parse_age_years(current_value):
                eq.age_basis = "estimated_manual"
        else:
            setattr(eq, field, new_value)

        try:
            update_equipment(self.conn, eq)
            self._do_search()
            self._update_status_bar()
            self._schedule_shared_sync()
        except Exception as exc:
            QMessageBox.critical(self, "Quick Edit Error", f"Failed to update {label}:\n{exc}")

    def _on_add(self) -> None:
        from Code.gui.add_edit_dialog import AddEditDialog

        dialog = AddEditDialog(self.conn, parent=self)
        if dialog.exec():
            self._do_search()
            self._update_status_bar()
            self._schedule_shared_sync()

    def _set_row_archived(self, row: int, archived: bool) -> None:
        """Archive or restore the selected record and refresh the current view."""
        eq = self._equipment_for_row(row)
        if eq is None or eq.is_archived == archived:
            return

        title = "Restore Record" if archived is False else "Archive Record"
        action_label = "restore this record from the archive" if archived is False else "archive this record"
        detail = (
            "The record will move back to the main Inventory view."
            if archived is False
            else "The record will be removed from Inventory and moved into the Archive view."
        )
        reply = QMessageBox.question(
            self,
            title,
            f"Do you want to {action_label}?\n\n{detail}",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        eq.is_archived = archived
        try:
            update_equipment(self.conn, eq)
            self._do_search()
            self._update_status_bar()
            self._schedule_shared_sync()
            status = "Record restored from archive." if not archived else "Record archived."
            self.status_bar.showMessage(status, 3000)
        except Exception as exc:
            QMessageBox.critical(self, title, f"Could not update the archive state:\n{exc}")

    def _on_edit(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            return

        record_id = self.table.record_id_for_row(row)
        if record_id is None:
            return
        eq = get_equipment_by_id(self.conn, record_id)
        if eq is None:
            return

        from Code.gui.add_edit_dialog import AddEditDialog

        dialog = AddEditDialog(self.conn, equipment=eq, parent=self)
        if dialog.exec():
            self._do_search()
            self._update_status_bar()
            self._schedule_shared_sync()

    def _on_delete(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            return

        record_id = self.table.record_id_for_row(row)
        if record_id is None:
            return
        reply = QMessageBox.question(
            self,
            "Delete Equipment",
            f"Delete this equipment record? (ID {record_id})",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            delete_equipment(self.conn, record_id)
            self._do_search()
            self._update_status_bar()
            self._schedule_shared_sync()

    def _on_cell_clicked(self, row: int, column: int) -> None:
        """Handle single clicks on the verify action column."""
        if column == VERIFY_COL:
            self._toggle_verify(row)
            return

        if column >= DATA_COL_START:
            _, field, _ = self._columns[column - DATA_COL_START]
            if field == "links" and QApplication.keyboardModifiers() & Qt.ControlModifier:
                self._open_record_link(row)

    def _equipment_for_row(self, row: int) -> Equipment | None:
        """Fetch the equipment record represented by the given visible row."""
        record_id = self.table.record_id_for_row(row)
        if record_id is None:
            return None

        return get_equipment_by_id(self.conn, record_id)

    def _format_table_value(self, field: str, raw_value) -> str:
        """Convert raw field values into compact table text."""
        return format_table_value(field, raw_value)

    def _build_search_query(self, eq: Equipment, mode: str = "general") -> str:
        """Build a browser query for the selected equipment row."""
        return build_search_query(eq, mode=mode)

    def _search_equipment_online(self, row: int, mode: str = "general") -> None:
        """Open a browser search for the selected equipment row."""
        eq = self._equipment_for_row(row)
        if eq is None:
            return

        query = self._build_search_query(eq, mode=mode)
        if not query:
            self.status_bar.showMessage(
                "No searchable manufacturer, model, or description is available for this row.",
                4000,
            )
            return

        encoded_query = urllib.parse.quote_plus(query)
        url = QUrl(_SEARCH_URL_TEMPLATE.format(query=encoded_query))
        if not QDesktopServices.openUrl(url):
            QMessageBox.warning(self, "Search Error", "Could not open the browser for this search.")
            return

        action_label = "how-old search" if mode == "year" else "web search"
        self.status_bar.showMessage(f"Opened {action_label}: {query}", 4000)

    def _open_record_link(self, row: int) -> None:
        """Open the saved external link for the selected record."""
        eq = self._equipment_for_row(row)
        if eq is None:
            return

        link_text = (eq.links or "").strip()
        if not link_text:
            self.status_bar.showMessage("No link is saved for this record.", 4000)
            return

        url = QUrl.fromUserInput(link_text)
        if not url.isValid() or not url.scheme():
            self.status_bar.showMessage("This link is not in a valid format.", 4000)
            return

        if not QDesktopServices.openUrl(url):
            QMessageBox.warning(self, "Open Link", "Could not open the saved link.")
            return

        self.status_bar.showMessage(f"Opened link: {link_text}", 4000)

    def _show_link_hover_hint(self, position: QPoint) -> None:
        """Show an immediate hover hint for link cells."""
        item = self.table.itemAt(position)
        if item is None:
            self._clear_link_hover_hint()
            return

        column_index = item.column()
        if column_index < DATA_COL_START:
            self._clear_link_hover_hint()
            return

        _, field, _ = self._columns[column_index - DATA_COL_START]
        link_value = str(item.data(LINK_ROLE) or "").strip()
        if field != "links" or not link_value:
            self._clear_link_hover_hint()
            return

        cell_key = (item.row(), item.column())
        if self._hovered_link_cell == cell_key:
            return

        self._hovered_link_cell = cell_key
        QToolTip.showText(
            self.table.viewport().mapToGlobal(position),
            "Ctrl+Click to open",
            self.table.viewport(),
        )

    def _clear_link_hover_hint(self) -> None:
        """Hide the custom hover hint for link cells."""
        if self._hovered_link_cell is None:
            return
        self._hovered_link_cell = None
        QToolTip.hideText()

    def _toggle_verify(self, row: int) -> None:
        """Toggle the verified_in_survey flag for the equipment at this row."""
        item = self.table.item(row, VERIFY_COL)
        if item is None:
            return

        record_id = self.table.record_id_for_row(row)
        if record_id is None:
            return
        eq = get_equipment_by_id(self.conn, record_id)
        if eq is None:
            return

        eq.verified_in_survey = not eq.verified_in_survey

        try:
            update_equipment(self.conn, eq)
        except Exception as exc:
            QMessageBox.critical(self, "Verify Error", f"Failed to update verification:\n{exc}")
            return

        # Update the cell visually without a full table refresh
        if eq.verified_in_survey:
            item.setText("\u2713")
            item.setForeground(verified_color(self._theme_name, True))
        else:
            item.setText("")
            item.setForeground(verified_color(self._theme_name, False))

        self._update_status_bar()
        self._schedule_shared_sync()

    def _copy_equipment_info(self, row: int) -> None:
        """Copy an age-search phrase to the clipboard."""
        eq = self._equipment_for_row(row)
        if eq is None:
            return

        text = build_age_search_query(eq)
        if not text:
            self.status_bar.showMessage(
                "Nothing useful to copy for this row. Add a manufacturer, model, or description first.",
                4000,
            )
            return

        clipboard = QGuiApplication.clipboard()
        clipboard.setText(text)
        self.status_bar.showMessage(f"Copied how-old search: {text}", 3000)

    def _default_output_dir(self) -> str:
        """Return the default Output/ directory for exports and ensure it exists."""
        if is_compiled():
            out = executable_dir() / "Output"
        else:
            out = bundle_root() / "Output"
        out.mkdir(parents=True, exist_ok=True)
        return str(out)

    def _on_export(self) -> None:
        default = str(Path(self._default_output_dir()) / APP_CONFIG.excel_export_filename)
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Equipment to Excel",
            default,
            "Excel Files (*.xlsx)",
        )
        if not path:
            return

        try:
            from Code.utils.export import export_inventory

            export_inventory(self.conn, Path(path))
            QMessageBox.information(
                self,
                "Export Complete",
                f"Equipment data exported to:\n{path}",
            )
        except Exception as exc:
            QMessageBox.critical(self, "Export Error", f"Export failed:\n{exc}")

    def _on_export_html(self) -> None:
        default = str(Path(self._default_output_dir()) / APP_CONFIG.html_report_filename)
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Verified Equipment HTML Report",
            default,
            "HTML Files (*.html)",
        )
        if not path:
            return

        try:
            from Code.reporting.generate_verified_report import build_report, write_report_html
            from Code.utils.export import export_inventory

            output_path = Path(path)
            with tempfile.TemporaryDirectory() as temp_dir:
                workbook_path = Path(temp_dir) / APP_CONFIG.excel_export_filename
                export_inventory(self.conn, workbook_path)
                report = build_report(workbook_path)
                write_report_html(report, output_path)

            QMessageBox.information(
                self,
                "Export Complete",
                f"HTML report exported to:\n{path}",
            )
        except Exception as exc:
            QMessageBox.critical(self, "Export Error", f"HTML export failed:\n{exc}")

    def _on_import_data(self) -> None:
        workbook_label = "source workbook" if not APP_CONFIG.survey_source_file else "source spreadsheets"
        dialog = QMessageBox(self)
        apply_window_branding(dialog, "Import Data")
        dialog.setIcon(QMessageBox.Question)
        dialog.setText("Choose what to import into this computer's database.")
        dialog.setInformativeText(
            f"Excel import merges/adds from the {workbook_label}.\n"
            f"Database import copies data from a shared {APP_CONFIG.database_label} file."
        )
        excel_button = dialog.addButton("Merge Excel Files", QMessageBox.AcceptRole)
        db_button = dialog.addButton("Import .db File", QMessageBox.ActionRole)
        dialog.addButton(QMessageBox.Cancel)
        dialog.exec()

        clicked_button = dialog.clickedButton()
        if clicked_button == excel_button:
            self._on_reimport_from_excel()
        elif clicked_button == db_button:
            self._on_import_from_db_file()

    def _on_reimport_from_excel(self) -> None:
        if APP_CONFIG.survey_source_file:
            message = (
                "This will re-parse both Excel source files and merge them into this computer's database.\n"
                "Existing records stay in place, matching records are updated conservatively, and new records are added.\n\nContinue?"
            )
        else:
            message = (
                "This will re-parse the current Excel source workbook and merge it into this computer's database.\n"
                "Existing records stay in place, matching records are updated conservatively, and new records are added.\n\nContinue?"
            )
        reply = QMessageBox.question(
            self,
            "Import Data",
            message,
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        try:
            from Code.importer.pipeline import run_merge_import

            data_dir = resolve_data_dir()
            stats = run_merge_import(data_dir)
            self._do_search()
            self._update_status_bar()
            self._schedule_shared_sync()
            QMessageBox.information(
                self,
                "Import Complete",
                f"Parsed rows: {stats['parsed_records']}\n"
                f"Added records: {stats['added_records']}\n"
                f"Merged into existing: {stats['matched_records']}\n"
                f"Updated existing records: {stats['updated_records']}\n"
                f"Merge conflicts: {stats['merge_conflicts']}\n"
                f"Survey matched: {stats['survey_matched']}\n"
                f"Raw cells indexed: {stats['total_raw_cells']}\n"
                f"Issues: {stats['total_issues']}",
            )
        except Exception as exc:
            QMessageBox.critical(self, "Import Error", f"Import failed:\n{exc}")

    def _on_import_from_db_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            f"Choose {APP_CONFIG.display_name} Database",
            "",
            "SQLite Database (*.db *.sqlite *.sqlite3);;All Files (*)",
        )
        if not path:
            return

        reply = QMessageBox.question(
            self,
            "Import Database File",
            "This will replace this computer's current local database with the data from the selected file.\n"
            "After the import finishes, the selected file is no longer needed.\n"
            "Any local manual additions or edits will be lost.\n\nContinue?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        try:
            from pathlib import Path

            stats = import_database_snapshot(self.conn, Path(path))
            self._do_search()
            self._update_status_bar()
            QMessageBox.information(
                self,
                "Import Complete",
                f"Copied {stats['equipment_records']} equipment records into this computer's database.\n"
                f"Raw cells: {stats['raw_cells']}\n"
                f"Import issues: {stats['import_issues']}\n\n"
                "You can delete the shared .db file after this import.",
            )
        except Exception as exc:
            QMessageBox.critical(self, "Import Error", f"Import failed:\n{exc}")

    def _update_status_bar(self) -> None:
        try:
            stats = get_equipment_stats(self.conn)
            if _uses_me_inventory_status():
                self.status_bar.showMessage(
                    f"Total: {stats['total']}  |  "
                    f"Verified: {stats['verified_in_survey']}/{stats['total']}  |  "
                    f"Import Issues: {stats['import_issues']}"
                )
            else:
                self.status_bar.showMessage(
                    f"Total: {stats['total']}  |  "
                    f"Active: {stats['active']}  |  "
                    f"Calibrated: {stats['calibrated']}  |  "
                    f"Repair: {stats['repair']}  |  "
                    f"Scrapped: {stats['scrapped']}  |  "
                    f"Verified: {stats['verified_in_survey']}/{stats['total']}"
                )
        except Exception:
            self.status_bar.showMessage("Ready")


def active_filter_specs() -> list[tuple[str, str, str]]:
    """Return the active filter specs for the current app variant."""
    field_order = tuple(getattr(APP_CONFIG, "filter_fields", ()))
    if not field_order:
        return list(ALL_FILTER_SPECS)

    by_field = {field: (label, field, filter_type) for label, field, filter_type in ALL_FILTER_SPECS}
    return [by_field[field] for field in field_order if field in by_field]


def _show_age_search_actions() -> bool:
    """Return whether the current app should expose age-search context actions."""
    return bool(getattr(APP_CONFIG, "show_age_search_actions", True))


def _uses_me_inventory_status() -> bool:
    """Return whether the current app should use the simplified ME status summary."""
    return bool(
        getattr(APP_CONFIG, "enable_project_field", False)
        and not getattr(APP_CONFIG, "show_calibration_section", True)
    )

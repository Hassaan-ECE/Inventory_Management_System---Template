"""Single-page search-driven equipment lookup."""

import sqlite3
import tempfile
import urllib.parse
from pathlib import Path

from PySide6.QtCore import QEvent, QPoint, Qt, QTimer, QUrl
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
    COLUMNS,
    DATA_COL_START,
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
from Code.importer.normalizer import normalize_manufacturer
from Code.utils.equipment_fields import parse_age_years
from Code.utils.runtime_paths import bundle_root, executable_dir, is_compiled, resolve_data_dir

_SEARCH_URL_TEMPLATE = "https://www.google.com/search?q={query}"
QUICK_EDIT_OPTIONS = {
    "lifecycle_status": ["active", "repair", "scrapped", "missing", "rental"],
    "working_status": ["working", "limited", "not_working", "unknown"],
    "calibration_status": ["calibrated", "reference_only", "out_to_cal", "unknown"],
}
QUICK_EDIT_SUGGEST_FIELDS = {"manufacturer", "model", "description", "location"}


class MainWindow(QMainWindow):
    """One-page, search-first equipment lookup window."""

    def __init__(self, conn: sqlite3.Connection, initial_theme_name: str = DEFAULT_THEME_NAME, parent=None):
        super().__init__(parent)
        self.conn = conn
        self._theme_name = normalize_theme_name(initial_theme_name)
        self._column_widths = {index + DATA_COL_START: width for index, (_, _, width) in enumerate(COLUMNS)}

        self.setWindowTitle(APP_CONFIG.display_name)
        self._apply_initial_window_size()

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(250)
        self._timer.timeout.connect(self._do_search)

        self._setup_ui()
        self._do_search()

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

        add_btn = QPushButton("+ Add Equipment")
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
        self.search_input.setPlaceholderText(
            'Search equipment — type anything: model, serial, manufacturer, location, "scrapped", "calibrated"...'
        )
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

        filter_specs = [
            ("Asset #", "asset_number", "text"),
            ("Manufacturer", "manufacturer", "text"),
            ("Model", "model", "text"),
            ("Description", "description", "text"),
            ("Est. Age (Yrs)", "estimated_age_years", "text"),
            ("Status", "lifecycle_status", "combo"),
            ("Working", "working_status", "combo"),
            ("Calibration", "calibration_status", "combo"),
            ("Location", "location", "text"),
        ]

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

        header_view = self.table.horizontalHeader()
        header_view.setContextMenuPolicy(Qt.CustomContextMenu)
        header_view.customContextMenuRequested.connect(self._show_header_menu)

        self.table.viewport().setContextMenuPolicy(Qt.CustomContextMenu)
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

        not_found_btn = QPushButton("Add Equipment")
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
        if watched is self.table.viewport() and event.type() == QEvent.ContextMenu:
            self._show_cell_menu(event.pos())
            return True
        return super().eventFilter(watched, event)

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

    def _do_search(self) -> None:
        """Run the search query and populate the results table."""
        query = self.search_input.text().strip()
        filters = self._current_column_filter_values()
        results = search_equipment(
            self.conn,
            query,
            lifecycle=filters["lifecycle_status"],
            calibration=filters["calibration_status"],
            working=filters["working_status"],
            location=filters["location"],
            asset_number=filters["asset_number"],
            manufacturer=filters["manufacturer"],
            model=filters["model"],
            description=filters["description"],
            estimated_age_years=filters["estimated_age_years"],
        )
        self.table.set_theme_name(self._theme_name)
        self.table.set_color_rows_enabled(self.color_rows_checkbox.isChecked())
        self.table.populate(results)

        count = len(results)
        has_filters = self._has_active_column_filters()
        if not query:
            if has_filters:
                self.results_label.setText(f"Showing {count} filtered equipment records")
            else:
                self.results_label.setText(f"Showing all {count} equipment records")
            self.not_found_widget.hide()
        elif count > 0:
            suffix = " after column filters" if has_filters else ""
            self.results_label.setText(f'{count} result{"s" if count != 1 else ""} for "{query}"{suffix}')
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

        visible_count = sum(
            1 for col_idx in range(DATA_COL_START, self.table.columnCount())
            if not self.table.isColumnHidden(col_idx)
        )

        for col_offset, (label, _, default_width) in enumerate(COLUMNS):
            table_col = col_offset + DATA_COL_START
            action = menu.addAction(label)
            action.setCheckable(True)
            is_visible = not self.table.isColumnHidden(table_col)
            action.setChecked(is_visible)
            if is_visible and visible_count == 1:
                action.setEnabled(False)
            action.toggled.connect(
                lambda checked, idx=table_col, width=default_width: self._set_column_visible(idx, checked, width)
            )

        menu.exec(header.mapToGlobal(position))

    def _set_column_visible(self, column_index: int, visible: bool, default_width: int) -> None:
        """Toggle a table column while preserving at least one visible column."""
        currently_visible = not self.table.isColumnHidden(column_index)
        if currently_visible == visible:
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
            label, _, _ = COLUMNS[column_index - DATA_COL_START]
            quick_edit_action = menu.addAction(f"Edit {label}")

        open_record_action = menu.addAction("Open Full Record")
        menu.addSeparator()
        search_online_action = menu.addAction("Search Equipment Online")
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
        elif chosen_action == search_online_action:
            self._search_equipment_online(item.row())
        elif chosen_action == search_year_action:
            self._search_equipment_online(item.row(), mode="year")
        elif chosen_action == copy_info_action:
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

        label, field, _ = COLUMNS[column_index - DATA_COL_START]
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
        except Exception as exc:
            QMessageBox.critical(self, "Quick Edit Error", f"Failed to update {label}:\n{exc}")

    def _on_add(self) -> None:
        from Code.gui.add_edit_dialog import AddEditDialog

        dialog = AddEditDialog(self.conn, parent=self)
        if dialog.exec():
            self._do_search()
            self._update_status_bar()

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

    def _on_cell_clicked(self, row: int, column: int) -> None:
        """Handle single clicks on the verify action column."""
        if column == VERIFY_COL:
            self._toggle_verify(row)

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
        dialog = QMessageBox(self)
        dialog.setWindowTitle("Import Data")
        dialog.setIcon(QMessageBox.Question)
        dialog.setText("Choose what to import into this computer's database.")
        dialog.setInformativeText(
            "Excel import merges/adds from the source spreadsheets.\n"
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
        reply = QMessageBox.question(
            self,
            "Import Data",
            "This will re-parse both Excel source files and merge them into this computer's database.\n"
            "Existing records stay in place, matching records are updated conservatively, and new records are added.\n\nContinue?",
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

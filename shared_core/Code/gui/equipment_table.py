"""Equipment results table widget and rendering helpers."""

from functools import cmp_to_key
from urllib.parse import urlparse

from app_config import APP_CONFIG
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QHeaderView, QTableWidget, QTableWidgetItem

from Code.db.models import Equipment
from Code.gui.theme import (
    calibration_color as theme_calibration_color,
    lifecycle_color as theme_lifecycle_color,
    row_background_color as theme_row_background_color,
    verified_color as theme_verified_color,
    working_color as theme_working_color,
)
from Code.utils.equipment_fields import format_age_years


ALL_COLUMNS = [
    ("Asset #", "asset_number", 130),
    ("Qty", "qty", 70),
    ("Manufacturer", "manufacturer", 120),
    ("Model", "model", 120),
    ("Description", "description", 250),
    ("Project", "project_name", 160),
    ("Est. Age (Yrs)", "estimated_age_years", 105),
    ("Status", "lifecycle_status", 90),
    ("Working", "working_status", 90),
    ("Calibration", "calibration_status", 110),
    ("Location", "location", 160),
    ("Links", "links", 220),
]

VERIFY_COL = 0
DATA_COL_START = 1
EMPTY_CELL_TEXT = " - "
SORT_ROLE = Qt.UserRole + 1
LINK_ROLE = Qt.UserRole + 2


class EquipmentTable(QTableWidget):
    """Configured table for displaying equipment records."""

    def __init__(self, theme_name: str, parent=None):
        super().__init__(parent)
        self._theme_name = theme_name
        self._color_rows_enabled = True
        self._columns = active_columns()
        self._sort_column = DATA_COL_START
        self._sort_order = Qt.AscendingOrder
        self._syncing_header_widths = False
        self._applied_startup_width_layout = False

        self.setColumnCount(len(self._columns) + DATA_COL_START)
        self.setHorizontalHeaderLabels(["\u2713"] + [column[0] for column in self._columns])
        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QTableWidget.SelectRows)
        self.setSelectionMode(QTableWidget.SingleSelection)
        self.setEditTriggers(QTableWidget.NoEditTriggers)
        self.setSortingEnabled(False)
        self.verticalHeader().setVisible(False)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setWordWrap(False)

        header_view = self.horizontalHeader()
        header_view.setStretchLastSection(False)
        header_view.setSectionResizeMode(QHeaderView.Interactive)
        header_view.setMinimumSectionSize(36)
        header_view.setSectionsMovable(False)
        header_view.setSectionsClickable(True)
        header_view.setSortIndicatorShown(True)
        header_view.sectionClicked.connect(self._on_header_clicked)
        header_view.sectionResized.connect(self._on_section_resized)
        header_view.setSortIndicator(self._sort_column, self._sort_order)

        self._column_min_widths = self._build_column_min_widths()

        for index, (_, _, width) in enumerate(self._columns):
            column = index + DATA_COL_START
            self.setColumnWidth(column, max(width, self._minimum_width_for_column(column)))

        self.setColumnWidth(VERIFY_COL, 40)
        header_view.setSectionResizeMode(VERIFY_COL, QHeaderView.Fixed)
        self._apply_default_hidden_columns()
        self._sync_header_resize_modes()

    def set_theme_name(self, theme_name: str) -> None:
        """Update the theme used for row rendering."""
        self._theme_name = theme_name

    def set_color_rows_enabled(self, enabled: bool) -> None:
        """Enable or disable lifecycle-based row coloring."""
        self._color_rows_enabled = enabled

    def populate(self, equipment: list[Equipment]) -> None:
        """Fill the results table with equipment rows."""
        self.clearSelection()
        self.setRowCount(len(equipment))

        for row_index, eq in enumerate(equipment):
            row_background = (
                _row_background(self._theme_name, eq.lifecycle_status)
                if self._color_rows_enabled
                else None
            )

            verify_item = QTableWidgetItem("\u2713" if eq.verified_in_survey else "")
            verify_item.setTextAlignment(Qt.AlignCenter)
            verify_item.setFlags(verify_item.flags() & ~Qt.ItemIsEditable)
            verify_item.setData(Qt.UserRole, eq.record_id)
            verify_item.setForeground(QColor(theme_verified_color(self._theme_name, eq.verified_in_survey)))
            verify_item.setToolTip("Click to mark this row as verified.")
            if row_background is not None:
                verify_item.setBackground(row_background)
            self.setItem(row_index, VERIFY_COL, verify_item)

            for column_index, (_, field, _) in enumerate(self._columns):
                raw_value = getattr(eq, field, "")
                if raw_value is None:
                    raw_value = ""
                value = format_table_value(field, raw_value)
                display_text = _format_links_display(value) if field == "links" else value
                display_value = display_text if display_text else EMPTY_CELL_TEXT
                item = SortableTableWidgetItem(display_value)
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                item.set_sort_value(sort_value(field, raw_value, value))
                if field == "links":
                    item.setData(LINK_ROLE, value)

                if not value:
                    item.setTextAlignment(Qt.AlignCenter)

                if row_background is not None:
                    item.setBackground(row_background)

                if field == "lifecycle_status":
                    item.setForeground(_lifecycle_color(self._theme_name, value))
                elif field == "working_status":
                    item.setForeground(_working_color(self._theme_name, value))
                elif field == "calibration_status":
                    item.setForeground(_cal_color(self._theme_name, value))

                self.setItem(row_index, column_index + DATA_COL_START, item)

        self._sort_rows(self._sort_column, self._sort_order)

    def sortItems(self, column: int, order: Qt.SortOrder = Qt.AscendingOrder) -> None:
        """Sort rows manually so blanks always remain at the bottom."""
        self._sort_column = column
        self._sort_order = order
        self.horizontalHeader().setSortIndicator(column, order)
        self._sort_rows(column, order)

    def _on_header_clicked(self, column: int) -> None:
        """Toggle and apply manual sorting when the user clicks a header."""
        if self._sort_column == column:
            next_order = Qt.DescendingOrder if self._sort_order == Qt.AscendingOrder else Qt.AscendingOrder
        else:
            next_order = Qt.AscendingOrder
        self.sortItems(column, next_order)

    def _sort_rows(self, column: int, order: Qt.SortOrder) -> None:
        """Apply the custom row sort implementation."""
        rows: list[list[QTableWidgetItem | None]] = []
        for row in range(self.rowCount()):
            rows.append([self.takeItem(row, col) for col in range(self.columnCount())])

        reverse = order == Qt.DescendingOrder
        rows.sort(key=cmp_to_key(lambda left, right: _compare_rows(left, right, column, reverse)))

        self.setRowCount(len(rows))
        for row_index, row_items in enumerate(rows):
            for col_index, item in enumerate(row_items):
                if item is not None:
                    self.setItem(row_index, col_index, item)

    def record_id_for_row(self, row: int) -> int | None:
        """Return the record id stored on the verify column for a row."""
        item = self.item(row, VERIFY_COL)
        if item is None:
            return None
        return item.data(Qt.UserRole)

    def _apply_default_hidden_columns(self) -> None:
        """Hide app-configured columns on first render."""
        hidden_fields = set(getattr(APP_CONFIG, "default_hidden_table_fields", ()))
        for index, (_, field, _) in enumerate(self._columns):
            self.setColumnHidden(index + DATA_COL_START, field in hidden_fields)

    def setColumnWidth(self, column: int, width: int) -> None:
        """Clamp visible columns so they never shrink below their header-based minimum."""
        if hasattr(self, "_column_min_widths") and column >= DATA_COL_START and not self.isColumnHidden(column):
            width = max(width, self._minimum_width_for_column(column))
        super().setColumnWidth(column, width)

    def setColumnHidden(self, column: int, hide: bool) -> None:
        """Keep hidden columns off to the right and visible columns packed left."""
        super().setColumnHidden(column, hide)
        self._sync_header_visual_order()
        self._sync_header_resize_modes()

    def _sync_header_resize_modes(self) -> None:
        """Lock the last visible data column to the right edge."""
        header_view = self.horizontalHeader()
        header_view.setSectionResizeMode(VERIFY_COL, QHeaderView.Fixed)

        visible_data_columns = [
            column
            for column in range(DATA_COL_START, self.columnCount())
            if not self.isColumnHidden(column)
        ]
        visible_verify_columns = [] if self.isColumnHidden(VERIFY_COL) else [VERIFY_COL]
        hidden_verify_columns = [VERIFY_COL] if self.isColumnHidden(VERIFY_COL) else []
        hidden_data_columns = [
            column
            for column in range(DATA_COL_START, self.columnCount())
            if self.isColumnHidden(column)
        ]
        if not visible_data_columns:
            return

        for column in visible_data_columns[:-1]:
            header_view.setSectionResizeMode(column, QHeaderView.Interactive)

        header_view.setSectionResizeMode(visible_data_columns[-1], QHeaderView.Fixed)
        for column in visible_verify_columns:
            header_view.setSectionResizeMode(column, QHeaderView.Fixed)
        for column in hidden_verify_columns:
            header_view.setSectionResizeMode(column, QHeaderView.Fixed)
        for column in hidden_data_columns:
            header_view.setSectionResizeMode(column, QHeaderView.Fixed)
        self._fit_columns_to_viewport()

    def _sync_header_visual_order(self) -> None:
        """Keep visible data columns in logical order and move hidden ones after them."""
        header_view = self.horizontalHeader()
        desired_order = []
        if not self.isColumnHidden(VERIFY_COL):
            desired_order.append(VERIFY_COL)
        desired_order.extend(
            column
            for column in range(DATA_COL_START, self.columnCount())
            if not self.isColumnHidden(column)
        )
        if self.isColumnHidden(VERIFY_COL):
            desired_order.append(VERIFY_COL)
        desired_order.extend(
            column
            for column in range(DATA_COL_START, self.columnCount())
            if self.isColumnHidden(column)
        )

        for visual_index, logical_index in enumerate(desired_order):
            current_index = header_view.visualIndex(logical_index)
            if current_index != visual_index:
                header_view.moveSection(current_index, visual_index)

    def resizeEvent(self, event) -> None:
        """Keep visible columns fitted inside the table viewport."""
        super().resizeEvent(event)
        if not self._applied_startup_width_layout and self.viewport().width() > 0:
            self._apply_startup_width_layout()
            self._applied_startup_width_layout = True
        self._fit_columns_to_viewport()

    def _build_column_min_widths(self) -> dict[int, int]:
        """Compute a minimum width for each data column from its header text."""
        header_view = self.horizontalHeader()
        metrics = header_view.fontMetrics()
        minimum_widths = {VERIFY_COL: 40}
        base_minimum = header_view.minimumSectionSize()
        extra_padding = 28
        for column in range(DATA_COL_START, self.columnCount()):
            item = self.horizontalHeaderItem(column)
            title = item.text() if item is not None else ""
            minimum_widths[column] = max(base_minimum, metrics.horizontalAdvance(title) + extra_padding)
        return minimum_widths

    def _minimum_width_for_column(self, column: int) -> int:
        """Return the configured minimum width for a table column."""
        return self._column_min_widths.get(column, self.horizontalHeader().minimumSectionSize())

    def _apply_startup_width_layout(self) -> None:
        """Apply the default startup column layout for the current app variant."""
        if not _uses_me_even_startup_widths():
            return

        visible_data_columns = [
            column
            for column in range(DATA_COL_START, self.columnCount())
            if not self.isColumnHidden(column)
        ]
        if len(visible_data_columns) < 2:
            return

        qty_column = next(
            (
                DATA_COL_START + index
                for index, (_, field, _) in enumerate(self._columns)
                if field == "qty" and not self.isColumnHidden(DATA_COL_START + index)
            ),
            None,
        )
        if qty_column is None:
            return

        other_columns = [column for column in visible_data_columns if column != qty_column]
        if not other_columns:
            return

        verify_width = self.columnWidth(VERIFY_COL) if not self.isColumnHidden(VERIFY_COL) else 0
        available_width = self.viewport().width() - verify_width
        if available_width <= 0:
            return

        qty_width = self._minimum_width_for_column(qty_column)
        remaining_width = max(0, available_width - qty_width)
        even_width = remaining_width // len(other_columns)

        self._syncing_header_widths = True
        try:
            self.setColumnWidth(qty_column, qty_width)
            for column in other_columns:
                self.setColumnWidth(column, max(self._minimum_width_for_column(column), even_width))
        finally:
            self._syncing_header_widths = False

    def _on_section_resized(self, section: int, _old_size: int, _new_size: int) -> None:
        """Clamp column resizes so the table stays within the viewport."""
        if self._syncing_header_widths or section < DATA_COL_START or self.isColumnHidden(section):
            return
        self._fit_columns_to_viewport(preferred_column=section)

    def _fit_columns_to_viewport(self, preferred_column: int | None = None) -> None:
        """Clamp interactive column widths and pin the last visible column to the viewport edge."""
        if self._syncing_header_widths:
            return

        visible_data_columns = [
            column
            for column in range(DATA_COL_START, self.columnCount())
            if not self.isColumnHidden(column)
        ]
        if not visible_data_columns:
            return

        verify_width = self.columnWidth(VERIFY_COL) if not self.isColumnHidden(VERIFY_COL) else 0
        available_width = self.viewport().width() - verify_width
        if available_width <= 0:
            return

        last_visible_column = visible_data_columns[-1]
        interactive_columns = visible_data_columns[:-1]
        widths = {
            column: max(self.columnWidth(column), self._minimum_width_for_column(column))
            for column in visible_data_columns
        }

        if preferred_column in interactive_columns:
            other_width = sum(widths[column] for column in interactive_columns if column != preferred_column)
            max_width = available_width - other_width - self._minimum_width_for_column(last_visible_column)
            widths[preferred_column] = min(
                widths[preferred_column],
                max(self._minimum_width_for_column(preferred_column), max_width),
            )

        overflow = (
            sum(widths[column] for column in interactive_columns)
            + self._minimum_width_for_column(last_visible_column)
            - available_width
        )
        if overflow > 0:
            shrink_order = []
            if preferred_column in interactive_columns:
                shrink_order.append(preferred_column)
            shrink_order.extend(
                column for column in reversed(interactive_columns) if column != preferred_column
            )
            for column in shrink_order:
                shrink_capacity = widths[column] - self._minimum_width_for_column(column)
                if shrink_capacity <= 0:
                    continue
                shrink_amount = min(shrink_capacity, overflow)
                widths[column] -= shrink_amount
                overflow -= shrink_amount
                if overflow <= 0:
                    break

        trailing_width = available_width - sum(widths[column] for column in interactive_columns)
        widths[last_visible_column] = max(
            self._minimum_width_for_column(last_visible_column),
            trailing_width,
        )

        self._syncing_header_widths = True
        try:
            for column in interactive_columns:
                if self.columnWidth(column) != widths[column]:
                    self.setColumnWidth(column, widths[column])
            if self.columnWidth(last_visible_column) != widths[last_visible_column]:
                self.setColumnWidth(last_visible_column, widths[last_visible_column])
        finally:
            self._syncing_header_widths = False

class SortableTableWidgetItem(QTableWidgetItem):
    """Table item that sorts by an explicit key when available."""

    def set_sort_value(self, value) -> None:
        self.setData(SORT_ROLE, value)

    def __lt__(self, other) -> bool:
        self_value = self.data(SORT_ROLE)
        other_value = other.data(SORT_ROLE)

        if self_value is not None and other_value is not None:
            return self_value < other_value

        return super().__lt__(other)


def format_table_value(field: str, raw_value) -> str:
    """Convert raw field values into compact table text."""
    if field == "estimated_age_years":
        return format_age_years(raw_value)
    if field == "qty":
        try:
            number = float(raw_value)
        except (TypeError, ValueError):
            return str(raw_value).strip()
        if number.is_integer():
            return str(int(number))
        return str(number)

    return str(raw_value).strip()


def sort_value(field: str, raw_value, display_value: str):
    """Build a stable sort key for table values."""
    if field in {"estimated_age_years", "qty"}:
        try:
            return (0, float(raw_value))
        except (TypeError, ValueError):
            return (1, float("inf"))

    normalized = display_value.strip().casefold()
    if normalized:
        return (0, normalized)
    return (1, "")


def _format_links_display(value: str) -> str:
    """Return a shorter display label for long URLs while preserving the real link elsewhere."""
    text = value.strip()
    if not text:
        return ""

    parsed = urlparse(text)
    if parsed.scheme and parsed.netloc:
        path = parsed.path.rstrip("/")
        compact = parsed.netloc
        if path:
            compact += path
        if len(compact) <= 54:
            return compact
        return f"{compact[:51]}..."

    if len(text) <= 54:
        return text
    return f"{text[:51]}..."


def _is_blank_sort_item(item: QTableWidgetItem | None) -> bool:
    """Return whether the item represents an empty display value."""
    if item is None:
        return True

    sort_key = item.data(SORT_ROLE)
    if isinstance(sort_key, tuple) and sort_key and sort_key[0] == 1:
        return True

    text = item.text().strip()
    return not text or text == EMPTY_CELL_TEXT.strip()


def _compare_rows(
    left: list[QTableWidgetItem | None],
    right: list[QTableWidgetItem | None],
    column: int,
    reverse: bool,
) -> int:
    """Compare two table rows while keeping blanks at the bottom."""
    left_item = left[column] if 0 <= column < len(left) else None
    right_item = right[column] if 0 <= column < len(right) else None

    left_blank = _is_blank_sort_item(left_item)
    right_blank = _is_blank_sort_item(right_item)
    if left_blank and right_blank:
        return 0
    if left_blank:
        return 1
    if right_blank:
        return -1

    left_value = left_item.data(SORT_ROLE) if left_item is not None else None
    right_value = right_item.data(SORT_ROLE) if right_item is not None else None

    comparison = _compare_values(left_value, right_value)
    if comparison == 0:
        left_text = left_item.text().casefold() if left_item is not None else ""
        right_text = right_item.text().casefold() if right_item is not None else ""
        comparison = _compare_values(left_text, right_text)

    return -comparison if reverse else comparison


def _compare_values(left, right) -> int:
    """Return a standard comparator result for two values."""
    if left == right:
        return 0
    if left is None:
        return -1
    if right is None:
        return 1
    return -1 if left < right else 1


def lifecycle_color(theme_name: str, value: str) -> QColor:
    return QColor(theme_lifecycle_color(theme_name, value))


def verified_color(theme_name: str, value: bool) -> QColor:
    return QColor(theme_verified_color(theme_name, value))


def working_color(theme_name: str, value: str) -> QColor:
    return QColor(theme_working_color(theme_name, value))


def calibration_color(theme_name: str, value: str) -> QColor:
    return QColor(theme_calibration_color(theme_name, value))


def row_background(theme_name: str, value: str) -> QColor:
    return QColor(theme_row_background_color(theme_name, value))


def _lifecycle_color(theme_name: str, value: str) -> QColor:
    return lifecycle_color(theme_name, value)


def _working_color(theme_name: str, value: str) -> QColor:
    return working_color(theme_name, value)


def _cal_color(theme_name: str, value: str) -> QColor:
    return calibration_color(theme_name, value)


def _row_background(theme_name: str, value: str) -> QColor:
    return row_background(theme_name, value)


def active_columns() -> list[tuple[str, str, int]]:
    """Return the active visible columns for the current app variant."""
    field_order = tuple(getattr(APP_CONFIG, "table_fields", ()))
    if not field_order:
        return list(ALL_COLUMNS)

    by_field = {field: (label, field, width) for label, field, width in ALL_COLUMNS}
    return [by_field[field] for field in field_order if field in by_field]


def _uses_me_even_startup_widths() -> bool:
    """Return whether the current app should evenly distribute startup widths after Qty."""
    return bool(
        getattr(APP_CONFIG, "enable_project_field", False)
        and not getattr(APP_CONFIG, "show_calibration_section", True)
    )


COLUMNS = active_columns()

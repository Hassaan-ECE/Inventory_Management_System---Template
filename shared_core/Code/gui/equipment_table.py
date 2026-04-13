"""Equipment results table widget and rendering helpers."""

from functools import cmp_to_key

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


COLUMNS = [
    ("Asset #", "asset_number", 130),
    ("Manufacturer", "manufacturer", 120),
    ("Model", "model", 120),
    ("Description", "description", 250),
    ("Est. Age (Yrs)", "estimated_age_years", 105),
    ("Status", "lifecycle_status", 90),
    ("Working", "working_status", 90),
    ("Calibration", "calibration_status", 110),
    ("Location", "location", 160),
]

VERIFY_COL = 0
DATA_COL_START = 1
EMPTY_CELL_TEXT = " - "
SORT_ROLE = Qt.UserRole + 1


class EquipmentTable(QTableWidget):
    """Configured table for displaying equipment records."""

    def __init__(self, theme_name: str, parent=None):
        super().__init__(parent)
        self._theme_name = theme_name
        self._color_rows_enabled = True
        self._sort_column = DATA_COL_START
        self._sort_order = Qt.AscendingOrder

        self.setColumnCount(len(COLUMNS) + DATA_COL_START)
        self.setHorizontalHeaderLabels(["\u2713"] + [column[0] for column in COLUMNS])
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
        header_view.setSortIndicator(self._sort_column, self._sort_order)

        description_index = DATA_COL_START + next(
            index for index, (_, field, _) in enumerate(COLUMNS)
            if field == "description"
        )
        header_view.setSectionResizeMode(description_index, QHeaderView.Stretch)

        for index, (_, _, width) in enumerate(COLUMNS):
            self.setColumnWidth(index + DATA_COL_START, width)

        self.setColumnWidth(VERIFY_COL, 40)
        header_view.setSectionResizeMode(VERIFY_COL, QHeaderView.Fixed)

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

            for column_index, (_, field, _) in enumerate(COLUMNS):
                raw_value = getattr(eq, field, "")
                if raw_value is None:
                    raw_value = ""
                value = format_table_value(field, raw_value)
                display_value = value if value else EMPTY_CELL_TEXT
                item = SortableTableWidgetItem(display_value)
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                item.set_sort_value(sort_value(field, raw_value, value))

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

    return str(raw_value).strip()


def sort_value(field: str, raw_value, display_value: str):
    """Build a stable sort key for table values."""
    if field == "estimated_age_years":
        try:
            return (0, float(raw_value))
        except (TypeError, ValueError):
            return (1, float("inf"))

    normalized = display_value.strip().casefold()
    if normalized:
        return (0, normalized)
    return (1, "")


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

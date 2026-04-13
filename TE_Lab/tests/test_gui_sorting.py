"""Regression tests for GUI table sorting behavior."""

import unittest

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from Code.db.models import Equipment
from Code.gui.equipment_table import COLUMNS, DATA_COL_START, EquipmentTable


class EquipmentTableSortingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_age_sort_keeps_blanks_at_bottom_in_both_directions(self) -> None:
        table = EquipmentTable("light")
        table.populate([
            Equipment(record_id=1, estimated_age_years=69),
            Equipment(record_id=2, estimated_age_years=None),
            Equipment(record_id=3, estimated_age_years=7),
            Equipment(record_id=4, estimated_age_years=57),
            Equipment(record_id=5, estimated_age_years=None),
        ])

        age_column = DATA_COL_START + next(
            index for index, (_, field, _) in enumerate(COLUMNS)
            if field == "estimated_age_years"
        )

        table.sortItems(age_column, Qt.AscendingOrder)
        self.assertEqual(self._column_values(table, age_column), ["7", "57", "69", "-", "-"])

        table.sortItems(age_column, Qt.DescendingOrder)
        self.assertEqual(self._column_values(table, age_column), ["69", "57", "7", "-", "-"])

    def test_text_sort_keeps_blanks_at_bottom_in_both_directions(self) -> None:
        table = EquipmentTable("light")
        table.populate([
            Equipment(record_id=1, manufacturer="Tektronix"),
            Equipment(record_id=2, manufacturer=""),
            Equipment(record_id=3, manufacturer="Fluke"),
            Equipment(record_id=4, manufacturer="Keysight"),
            Equipment(record_id=5, manufacturer=""),
        ])

        manufacturer_column = DATA_COL_START + next(
            index for index, (_, field, _) in enumerate(COLUMNS)
            if field == "manufacturer"
        )

        table.sortItems(manufacturer_column, Qt.AscendingOrder)
        self.assertEqual(
            self._column_values(table, manufacturer_column),
            ["Fluke", "Keysight", "Tektronix", "-", "-"],
        )

        table.sortItems(manufacturer_column, Qt.DescendingOrder)
        self.assertEqual(
            self._column_values(table, manufacturer_column),
            ["Tektronix", "Keysight", "Fluke", "-", "-"],
        )

    def _column_values(self, table: EquipmentTable, column: int) -> list[str]:
        values = []
        for row in range(table.rowCount()):
            item = table.item(row, column)
            values.append(item.text().strip() if item is not None else "")
        return values


if __name__ == "__main__":
    unittest.main()

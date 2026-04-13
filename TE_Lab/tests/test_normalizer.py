"""Unit tests for normalization and shared equipment helpers."""

import unittest

from Code.db.models import Equipment, parse_source_refs
from Code.importer.normalizer import infer_working_status, is_placeholder, normalize_manufacturer, parse_date
from Code.utils.equipment_fields import format_age_years, parse_age_years


class NormalizerTests(unittest.TestCase):
    def test_normalize_manufacturer_preserves_known_branding(self) -> None:
        self.assertEqual(normalize_manufacturer("hewlett-packard"), "HP")
        self.assertEqual(normalize_manufacturer("aglient"), "Agilent")
        self.assertEqual(normalize_manufacturer("Custom Vendor"), "Custom Vendor")

    def test_parse_date_handles_supported_formats(self) -> None:
        self.assertEqual(parse_date("1.15.24"), "2024-01-15")
        self.assertEqual(parse_date("01/15/2024"), "2024-01-15")
        self.assertEqual(parse_date("2024-01-15"), "2024-01-15")
        self.assertEqual(parse_date("ref only"), "")
        self.assertEqual(parse_date("bad-value"), "")

    def test_infer_working_status_covers_known_conditions(self) -> None:
        self.assertEqual(infer_working_status("functional"), "working")
        self.assertEqual(infer_working_status("intermittent output"), "limited")
        self.assertEqual(infer_working_status("broken display"), "not_working")
        self.assertEqual(infer_working_status("needs new probes"), "working")
        self.assertEqual(infer_working_status(""), "unknown")

    def test_is_placeholder_recognizes_common_non_values(self) -> None:
        self.assertTrue(is_placeholder("N/A"))
        self.assertTrue(is_placeholder("need asset no"))
        self.assertFalse(is_placeholder("A-100"))

    def test_age_helpers_parse_and_format_consistently(self) -> None:
        self.assertEqual(parse_age_years("10.5"), 10.5)
        self.assertEqual(parse_age_years(" 10 "), 10.0)
        self.assertIsNone(parse_age_years("-1"))
        self.assertEqual(format_age_years(10.0), "10")
        self.assertEqual(format_age_years(10.5), "10.5")
        self.assertEqual(format_age_years(None), "")

    def test_equipment_source_ref_helpers_are_safe(self) -> None:
        eq = Equipment(source_refs="not json")
        self.assertEqual(eq.parsed_source_refs(), [])
        self.assertEqual(eq.first_source_row(), 0)

        eq.add_source_ref("Master.xls", "All Equip", 12)
        eq.add_source_ref("Survey.xlsx", "Sheet1", 8)

        self.assertEqual(len(eq.parsed_source_refs()), 2)
        self.assertEqual(eq.first_source_row("All Equip"), 12)
        self.assertEqual(parse_source_refs('{"bad": "shape"}'), [])


if __name__ == "__main__":
    unittest.main()

"""Tests for the verified equipment HTML report generator."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from openpyxl import Workbook

from Code.reporting.generate_verified_report import build_report, write_report_html


class VerifiedReportTests(unittest.TestCase):
    def test_build_report_filters_to_verified_rows_only(self) -> None:
        workbook_path = self._create_workbook([
            {
                "Asset Number": "A-100",
                "Serial Number": "S-100",
                "Manufacturer": "Acme",
                "Model": "One",
                "Description": "Scope",
                "Location": "TE Lab",
                "Assigned To": "Chris",
                "Lifecycle": "active",
                "Working": "working",
                "Cal Status": "reference_only",
                "Blue Dot": "BD-1",
                "Est. Age (Yrs)": 4,
                "Notes": "Ready",
                "Verified": "Yes",
            },
            {
                "Asset Number": "A-200",
                "Serial Number": "S-200",
                "Manufacturer": "Acme",
                "Model": "Two",
                "Description": "Meter",
                "Location": "Storage",
                "Assigned To": "",
                "Lifecycle": "repair",
                "Working": "limited",
                "Cal Status": "out_to_cal",
                "Blue Dot": "",
                "Est. Age (Yrs)": 9,
                "Notes": "",
                "Verified": "",
            },
        ])

        report = build_report(workbook_path)

        self.assertEqual(len(report.rows), 1)
        self.assertEqual(report.rows[0]["Serial Number"], "S-100")
        self.assertEqual(report.by_location["TE Lab"], 1)
        self.assertEqual(report.by_lifecycle["active"], 1)

    def test_write_report_html_outputs_searchable_report(self) -> None:
        workbook_path = self._create_workbook([
            {
                "Asset Number": "A-100",
                "Serial Number": "S-100",
                "Manufacturer": "Acme",
                "Model": "One",
                "Description": "Scope",
                "Location": "TE Lab",
                "Assigned To": "Chris",
                "Lifecycle": "active",
                "Working": "working",
                "Cal Status": "reference_only",
                "Blue Dot": "BD-1",
                "Est. Age (Yrs)": 4,
                "Notes": "Ready",
                "Verified": "Yes",
            },
        ])
        report = build_report(workbook_path)

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "report.html"
            write_report_html(report, output_path)
            html = output_path.read_text(encoding="utf-8")

        self.assertIn("TE Lab Test Equipment Age Review", html)
        self.assertIn("Manager Action Summary", html)
        self.assertIn("Oldest Verified Equipment", html)
        self.assertIn("S-100", html)
        self.assertIn("row-select", html)
        self.assertIn("toggleFilters", html)
        self.assertIn("toggleColumns", html)
        self.assertNotIn("Recommended Action", html)
        self.assertNotIn("This report is for manager review", html)
        self.assertNotIn("No verified equipment found", html)

    def test_oldest_section_is_sorted_by_age_desc(self) -> None:
        workbook_path = self._create_workbook([
            {
                "Asset Number": "A-100",
                "Serial Number": "S-050",
                "Manufacturer": "Acme",
                "Model": "Oldest",
                "Description": "Scope",
                "Location": "TE Lab",
                "Assigned To": "",
                "Lifecycle": "active",
                "Working": "working",
                "Cal Status": "reference_only",
                "Blue Dot": "",
                "Est. Age (Yrs)": 50,
                "Notes": "",
                "Verified": "Yes",
            },
            {
                "Asset Number": "A-200",
                "Serial Number": "S-040",
                "Manufacturer": "Acme",
                "Model": "Scrapped",
                "Description": "Meter",
                "Location": "TE Lab",
                "Assigned To": "",
                "Lifecycle": "scrapped",
                "Working": "working",
                "Cal Status": "reference_only",
                "Blue Dot": "",
                "Est. Age (Yrs)": 40,
                "Notes": "",
                "Verified": "Yes",
            },
            {
                "Asset Number": "A-300",
                "Serial Number": "S-005",
                "Manufacturer": "Acme",
                "Model": "Newest",
                "Description": "Probe",
                "Location": "TE Lab",
                "Assigned To": "",
                "Lifecycle": "active",
                "Working": "working",
                "Cal Status": "reference_only",
                "Blue Dot": "",
                "Est. Age (Yrs)": 5,
                "Notes": "",
                "Verified": "Yes",
            },
        ])
        report = build_report(workbook_path)

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "report.html"
            write_report_html(report, output_path)
            html = output_path.read_text(encoding="utf-8")

        oldest_section_start = html.index("<h2>Oldest Verified Equipment</h2>")
        oldest_section_end = html.index("</article>", oldest_section_start)
        oldest_section = html[oldest_section_start:oldest_section_end]

        self.assertLess(oldest_section.index("S-050"), oldest_section.index("S-040"))
        self.assertLess(oldest_section.index("S-040"), oldest_section.index("S-005"))

    def test_detail_table_renders_sortable_headers_and_matching_select_filters(self) -> None:
        workbook_path = self._create_workbook([
            {
                "Asset Number": "A-100",
                "Serial Number": "S-100",
                "Manufacturer": "Acme",
                "Model": "One",
                "Description": "Scope",
                "Location": "TE Lab",
                "Assigned To": "",
                "Lifecycle": "active",
                "Working": "not_working",
                "Cal Status": "reference_only",
                "Blue Dot": "",
                "Est. Age (Yrs)": 12,
                "Notes": "",
                "Verified": "Yes",
            },
        ])
        report = build_report(workbook_path)

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "report.html"
            write_report_html(report, output_path)
            html = output_path.read_text(encoding="utf-8")

        self.assertIn('data-sortable="true"', html)
        self.assertIn('class="sort-button"', html)
        self.assertIn('aria-sort="none"', html)
        self.assertIn('<span class="header-label">Age</span>', html)
        self.assertIn('<option value="Not Working">Not Working</option>', html)
        self.assertIn('<option value="Reference Only">Reference Only</option>', html)
        self.assertIn('const isSelectFilter = control.tagName === "SELECT";', html)
        self.assertIn('(isSelectFilter && text !== value)', html)
        self.assertIn('.resize-handle::before', html)

    def _create_workbook(self, rows: list[dict[str, object]]) -> Path:
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)

        workbook_path = Path(temp_dir.name) / "inventory.xlsx"
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Inventory"

        headers = [
            "Asset Number",
            "Serial Number",
            "Manufacturer",
            "Model",
            "Description",
            "Location",
            "Assigned To",
            "Lifecycle",
            "Working",
            "Cal Status",
            "Blue Dot",
            "Est. Age (Yrs)",
            "Notes",
            "Verified",
        ]
        sheet.append(headers)

        for row in rows:
            sheet.append([row.get(header, "") for header in headers])

        workbook.save(workbook_path)
        return workbook_path


if __name__ == "__main__":
    unittest.main()

"""Parser for the Master List Excel workbook (.xls)."""
from pathlib import Path

import xlrd

from app_config import APP_CONFIG
from Code.db.models import Equipment, ImportIssue, RawCell
from Code.importer.matching import build_equipment_indexes, resolve_equipment_match
from Code.importer.normalizer import (
    clean_value, col_to_letter, higher_calibration, higher_lifecycle,
    infer_working_status, is_placeholder, normalize_manufacturer, parse_date,
)

MASTER_FILE = APP_CONFIG.master_source_file

# ── Column name aliases → canonical field names ─────────────────────────────

COLUMN_ALIASES: dict[str, str] = {
    "asset number":              "asset_number",
    "asset numbers":             "asset_number",
    "asset no.":                 "asset_number",
    "asset no":                  "asset_number",
    "asset #":                   "asset_number",
    "serial number":             "serial_number",
    "serial no":                 "serial_number",
    "sn":                        "serial_number",
    "manufacturer":              "manufacturer",
    "model":                     "model",
    "description":               "description",
    "qty":                       "qty",
    "last calibration date":     "last_calibration_date",
    "last cal":                  "last_calibration_date",
    "calibration due date":      "calibration_due_date",
    "cal due":                   "calibration_due_date",
    "expired?":                  "expired",
    "last calibrated by":        "calibration_vendor",
    "calibrated by":             "calibration_vendor",
    "location":                  "location",
    "assigned location":         "location",
    "assigned to":               "assigned_to",
    "condition":                 "condition",
    "current location":          "current_location",
    "calibration cost current":  "calibration_cost",
    "rental cost $/mo.":         "rental_cost",
    "vendor":                    "vendor",
    "note's":                    "notes",
    "notes":                     "notes",
}


def _find_header_row(sheet: xlrd.sheet.Sheet, max_rows: int = 10) -> tuple[int, dict[str, int]]:
    """Find the header row and build a column-name → index map.

    Returns (header_row_index, {canonical_field: col_index}).
    """
    for r in range(min(max_rows, sheet.nrows)):
        row_vals = [clean_value(sheet.cell_value(r, c)).lower() for c in range(sheet.ncols)]
        # A header row must contain "asset" somewhere (every equipment sheet has this)
        if any("asset" in v for v in row_vals):
            col_map = {}
            for c, val in enumerate(row_vals):
                canonical = COLUMN_ALIASES.get(val)
                if canonical and canonical not in col_map:
                    col_map[canonical] = c
            if "asset_number" in col_map:
                return r, col_map
    return -1, {}


def _row_to_dict(sheet: xlrd.sheet.Sheet, row_idx: int,
                 col_map: dict[str, int]) -> dict[str, str]:
    """Extract a single data row as a {field: value} dict."""
    result = {}
    for field, c in col_map.items():
        if c < sheet.ncols:
            result[field] = clean_value(sheet.cell_value(row_idx, c))
        else:
            result[field] = ""
    return result


def _is_empty_row(row_dict: dict[str, str]) -> bool:
    """Check if a row dict has no meaningful values."""
    return all(not v or is_placeholder(v) for v in row_dict.values())


# ── Sheets to import as normalized equipment ────────────────────────────────

# sheet_name → what it implies about the equipment
OVERLAY_SHEETS = {
    "All Calibration":  {"calibration_status": "calibrated"},
    "May Cal":          {"calibration_status": "calibrated"},
    "Oct Cal":          {"calibration_status": "calibrated"},
    "2024 New Cal":     {"calibration_status": "calibrated"},
    "Non Cal":          {"calibration_status": "reference_only"},
    "Repair":           {"lifecycle_status": "repair"},
    "Scrapped":         {"lifecycle_status": "scrapped"},
    "Missing":          {"lifecycle_status": "missing"},
    "Rental":           {"lifecycle_status": "rental", "ownership_type": "rental"},
    "Out To Cal":       {"calibration_status": "out_to_cal"},
}

# Sheets that are only indexed for raw search (not normalized import)
RAW_ONLY_SHEETS = {
    "Cal Changes 10..1.17", "China", "DELTA", "Shunt Cal",
    "Sheet1", "Sheet2", "Sheet3", "Sheet4", "Sheet5", "Sheet6",
    "Lab Computers", "Hand Tools",
}


def parse_base_sheet(wb_path: Path) -> tuple[list[Equipment], list[ImportIssue]]:
    """Parse 'All Equip' sheet as the base import.

    Returns (equipment_list, issues_list).
    """
    wb = xlrd.open_workbook(str(wb_path))
    sheet = wb.sheet_by_name("All Equip")
    header_row, col_map = _find_header_row(sheet)

    if header_row < 0:
        return [], [ImportIssue(
            issue_type="parse_error",
            source_file=MASTER_FILE, source_sheet="All Equip", source_row=0,
            summary="Could not find header row in All Equip sheet",
        )]

    equipment_list: list[Equipment] = []
    issues: list[ImportIssue] = []

    for r in range(header_row + 1, sheet.nrows):
        excel_row = r + 1
        row = _row_to_dict(sheet, r, col_map)
        if _is_empty_row(row):
            continue

        asset = row.get("asset_number", "")
        serial = row.get("serial_number", "")
        mfg_raw = row.get("manufacturer", "")

        # Flag rows with no asset number AND no serial number
        if is_placeholder(asset) and is_placeholder(serial):
            issues.append(ImportIssue(
                issue_type="missing_id",
                source_file=MASTER_FILE, source_sheet="All Equip", source_row=excel_row,
                asset_number=asset, serial_number=serial,
                summary=f"Row {excel_row}: no asset number and no serial number",
                raw_data=json.dumps(row),
            ))
            # Still import it — but flag it
            pass

        cond = row.get("condition", "")

        # Parse calibration cost
        cal_cost = None
        cost_str = row.get("calibration_cost", "")
        if cost_str and not is_placeholder(cost_str):
            try:
                cal_cost = float(cost_str)
            except ValueError:
                pass

        # Determine calibration status from the base sheet
        last_cal = parse_date(row.get("last_calibration_date", ""))
        cal_due = parse_date(row.get("calibration_due_date", ""))
        if is_placeholder(row.get("last_calibration_date", "")) and \
           is_placeholder(row.get("calibration_due_date", "")):
            cal_status = "reference_only"
        elif last_cal or cal_due:
            cal_status = "calibrated"
        else:
            cal_status = "unknown"

        eq = Equipment(
            asset_number=asset if not is_placeholder(asset) else "",
            serial_number=serial if not is_placeholder(serial) else "",
            manufacturer=normalize_manufacturer(mfg_raw),
            manufacturer_raw=mfg_raw,
            model=row.get("model", ""),
            description=row.get("description", ""),
            qty=_safe_float(row.get("qty", "")),
            location=row.get("location", ""),
            assigned_to=row.get("assigned_to", ""),
            calibration_status=cal_status,
            last_calibration_date=last_cal,
            calibration_due_date=cal_due,
            calibration_vendor=row.get("calibration_vendor", ""),
            calibration_cost=cal_cost,
            working_status=infer_working_status(cond),
            condition=cond,
        )
        eq.add_source_ref(MASTER_FILE, "All Equip", excel_row)
        equipment_list.append(eq)

    return equipment_list, issues


def parse_overlay_sheets(wb_path: Path, base_records: list[Equipment]
                         ) -> tuple[list[Equipment], list[ImportIssue]]:
    """Parse overlay sheets and merge status/data into base records.

    Matching is by asset_number first, then serial_number.
    Unmatched overlay rows become import issues.
    Returns the updated base_records and any new issues.
    """
    wb = xlrd.open_workbook(str(wb_path))
    issues: list[ImportIssue] = []

    by_asset, by_serial, by_import_key = build_equipment_indexes(base_records)

    for sheet_name, status_overrides in OVERLAY_SHEETS.items():
        if sheet_name not in wb.sheet_names():
            continue
        sheet = wb.sheet_by_name(sheet_name)
        header_row, col_map = _find_header_row(sheet)
        if header_row < 0:
            issues.append(ImportIssue(
                issue_type="parse_error",
                source_file=MASTER_FILE, source_sheet=sheet_name, source_row=0,
                summary=f"Could not find header row in '{sheet_name}'",
            ))
            continue

        for r in range(header_row + 1, sheet.nrows):
            excel_row = r + 1
            row = _row_to_dict(sheet, r, col_map)
            if _is_empty_row(row):
                continue

            asset = row.get("asset_number", "").strip()
            serial = row.get("serial_number", "").strip()

            match = resolve_equipment_match(by_asset, by_serial, by_import_key, asset, serial)
            if match.record is None:
                issues.append(ImportIssue(
                    issue_type=match.status,
                    source_file=MASTER_FILE, source_sheet=sheet_name, source_row=excel_row,
                    asset_number=asset, serial_number=serial,
                    summary=f"Row {excel_row} in '{sheet_name}' {match.summary}",
                    raw_data=json.dumps(row),
                ))
                continue
            matched = match.record

            # Apply status overrides
            if "lifecycle_status" in status_overrides:
                matched.lifecycle_status = higher_lifecycle(
                    matched.lifecycle_status, status_overrides["lifecycle_status"]
                )
            if "calibration_status" in status_overrides:
                matched.calibration_status = higher_calibration(
                    matched.calibration_status, status_overrides["calibration_status"]
                )
            if "ownership_type" in status_overrides:
                matched.ownership_type = status_overrides["ownership_type"]

            # Pull in rental-specific fields
            if sheet_name == "Rental":
                vendor = row.get("vendor", "")
                if vendor and not is_placeholder(vendor):
                    matched.rental_vendor = vendor
                cost = row.get("rental_cost", "")
                if cost and not is_placeholder(cost):
                    try:
                        matched.rental_cost_monthly = float(cost)
                    except ValueError:
                        pass
                notes = row.get("notes", "")
                if notes:
                    matched.notes = (matched.notes + " | " + notes).strip(" | ")

            # Pull in repair-specific fields
            if sheet_name == "Repair":
                cur_loc = row.get("current_location", "")
                if cur_loc:
                    matched.notes = (matched.notes + f" | Current location: {cur_loc}").strip(" | ")

            # Update calibration dates if overlay has newer info
            new_last_cal = parse_date(row.get("last_calibration_date", ""))
            if new_last_cal and new_last_cal > matched.last_calibration_date:
                matched.last_calibration_date = new_last_cal
            new_cal_due = parse_date(row.get("calibration_due_date", ""))
            if new_cal_due and new_cal_due > matched.calibration_due_date:
                matched.calibration_due_date = new_cal_due

            # Update calibration vendor
            new_vendor = row.get("calibration_vendor", "")
            if new_vendor and not is_placeholder(new_vendor):
                matched.calibration_vendor = new_vendor

            # Track the source reference
            matched.add_source_ref(MASTER_FILE, sheet_name, excel_row)

    return base_records, issues


def index_all_raw_cells(wb_path: Path) -> list[RawCell]:
    """Index every non-empty cell in every sheet for raw search."""
    wb = xlrd.open_workbook(str(wb_path))
    cells: list[RawCell] = []

    for sheet_name in wb.sheet_names():
        sheet = wb.sheet_by_name(sheet_name)
        for r in range(sheet.nrows):
            # Build row preview (first few non-empty cells)
            row_vals = []
            for c in range(min(sheet.ncols, 15)):
                v = clean_value(sheet.cell_value(r, c))
                if v:
                    row_vals.append(v)
            row_preview = " | ".join(row_vals[:6])

            for c in range(sheet.ncols):
                val = clean_value(sheet.cell_value(r, c))
                if val and not val.isspace():
                    cells.append(RawCell(
                        source_file=MASTER_FILE,
                        source_sheet=sheet_name,
                        row_number=r + 1,
                        column_number=c + 1,
                        cell_address=f"{col_to_letter(c)}{r + 1}",
                        cell_value=val,
                        row_preview=row_preview,
                    ))

    return cells


def _safe_float(value: str):
    """Convert to float or return None."""
    if not value or is_placeholder(value):
        return None
    try:
        return float(value)
    except ValueError:
        return None

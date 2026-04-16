"""Data models for TE Lab Equipment Inventory Manager."""

import json
from dataclasses import dataclass
from typing import Optional


@dataclass
class Equipment:
    """A normalized equipment record."""

    record_id: Optional[int] = None
    record_uuid: str = ""
    asset_number: str = ""
    serial_number: str = ""
    manufacturer: str = ""
    manufacturer_raw: str = ""
    model: str = ""
    description: str = ""
    qty: Optional[float] = None

    # Location / Ownership
    location: str = ""
    assigned_to: str = ""
    ownership_type: str = "owned"  # owned, rental, unknown
    rental_vendor: str = ""
    rental_cost_monthly: Optional[float] = None

    # Calibration
    calibration_status: str = "unknown"  # calibrated, reference_only, out_to_cal, unknown
    last_calibration_date: str = ""
    calibration_due_date: str = ""
    calibration_vendor: str = ""
    calibration_cost: Optional[float] = None

    # Lifecycle / Condition
    lifecycle_status: str = "active"  # active, repair, scrapped, missing, rental
    working_status: str = "unknown"  # working, limited, not_working, unknown
    condition: str = ""

    # Age / Audit
    acquired_date: str = ""
    estimated_age_years: Optional[float] = None
    age_basis: str = "unknown"  # exact, estimated_manual, survey, unknown
    verified_in_survey: bool = False
    blue_dot_ref: str = ""

    # Metadata
    project_name: str = ""
    picture_path: str = ""
    links: str = ""
    notes: str = ""
    manual_entry: bool = False
    is_archived: bool = False
    source_refs: str = "[]"  # JSON string: [{"file": ..., "sheet": ..., "row": ...}]
    created_at: str = ""
    updated_at: str = ""

    def parsed_source_refs(self) -> list[dict]:
        """Return source refs as a parsed list, falling back safely."""
        return parse_source_refs(self.source_refs)

    def set_parsed_source_refs(self, refs: list[dict]) -> None:
        """Persist parsed source refs back onto the model."""
        self.source_refs = json.dumps(refs)

    def add_source_ref(self, file: str, sheet: str, row: int, import_key: str = "") -> None:
        """Append a single source reference safely."""
        refs = self.parsed_source_refs()
        ref = {"file": file, "sheet": sheet, "row": row}
        if import_key:
            ref["import_key"] = import_key
        refs.append(ref)
        self.set_parsed_source_refs(refs)

    def first_source_row(self, sheet: str = "All Equip") -> int:
        """Return the first recorded row for the requested source sheet."""
        for ref in self.parsed_source_refs():
            if ref.get("sheet") != sheet:
                continue
            try:
                return int(ref.get("row", 0))
            except (TypeError, ValueError):
                return 0
        return 0

    def primary_import_key(self) -> str:
        """Return the first stable import key recorded in the source refs."""
        for ref in self.parsed_source_refs():
            value = str(ref.get("import_key", "")).strip()
            if value:
                return value
        return ""


@dataclass
class RawCell:
    """A single cell from a source Excel file, for raw search."""

    id: Optional[int] = None
    source_file: str = ""
    source_sheet: str = ""
    row_number: int = 0  # Excel 1-based row number
    column_number: int = 0  # Excel 1-based column number
    cell_address: str = ""
    cell_value: str = ""
    row_preview: str = ""


@dataclass
class ImportIssue:
    """A row that could not be cleanly imported."""

    id: Optional[int] = None
    issue_type: str = ""  # duplicate, unmatched, missing_id, placeholder, conflict
    source_file: str = ""
    source_sheet: str = ""
    source_row: int = 0
    asset_number: str = ""
    serial_number: str = ""
    summary: str = ""
    raw_data: str = ""  # JSON of the row data
    resolution_status: str = "unresolved"  # unresolved, resolved, ignored
    created_at: str = ""


def parse_source_refs(raw: str) -> list[dict]:
    """Parse source refs JSON safely."""
    if not raw:
        return []

    try:
        refs = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return []

    return refs if isinstance(refs, list) else []

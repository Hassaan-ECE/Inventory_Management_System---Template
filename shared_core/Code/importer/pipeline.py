"""Import pipeline — orchestrates parsing, normalization, matching, and loading into SQLite."""
import json
from pathlib import Path

from app_config import APP_CONFIG
from Code.db.database import (
    clear_all_data, create_tables, get_all_equipment, get_connection,
    insert_equipment, insert_import_issue, insert_raw_cells_batch, update_equipment,
)
from Code.db.models import Equipment, ImportIssue
from Code.importer.matching import build_equipment_indexes, resolve_equipment_match
from Code.importer.master_parser import (
    MASTER_FILE, index_all_raw_cells, parse_base_sheet, parse_overlay_sheets,
)
from Code.importer.me_parser import index_me_raw_cells, parse_me_workbook
from Code.importer.normalizer import is_placeholder
from Code.importer.survey_parser import SURVEY_FILE, index_survey_raw_cells, parse_survey


def run_full_import(data_dir: Path, db_path: Path | None = None,
                    progress_callback=None) -> dict:
    """Run the complete import pipeline.

    Args:
        data_dir: Path to the Data/ folder containing the Excel files.
        db_path: Optional path for the SQLite database. Uses default if None.
        progress_callback: Optional callable(step_name, detail) for progress updates.

    Returns a dict with import statistics.
    """
    master_path = data_dir / MASTER_FILE

    if not master_path.exists():
        raise FileNotFoundError(f"Master workbook not found: {master_path}")

    conn = get_connection(db_path)

    stats = {
        "base_records": 0,
        "overlay_issues": 0,
        "survey_matched": 0,
        "survey_unmatched": 0,
        "total_raw_cells": 0,
        "total_issues": 0,
    }

    all_issues: list[ImportIssue] = []

    try:
        create_tables(conn)
        conn.execute("BEGIN")
        clear_all_data(conn, commit=False)

        if _import_profile() == "me_single_workbook":
            _emit(progress_callback, "Parsing", "Reading ME inventory workbook...")
            imported_records, base_issues = parse_me_workbook(master_path)
            all_issues.extend(base_issues)
            stats["base_records"] = len(imported_records)

            _emit(progress_callback, "Saving", "Writing inventory records to database...")
            for eq in imported_records:
                insert_equipment(conn, eq, commit=False)

            _emit(progress_callback, "Issues", "Recording import issues...")
            for issue in all_issues:
                insert_import_issue(conn, issue, commit=False)
            stats["total_issues"] = len(all_issues)

            _emit(progress_callback, "Indexing", "Indexing ME workbook cells...")
            all_cells = index_me_raw_cells(master_path)
            stats["total_raw_cells"] = len(all_cells)

            batch_size = 5000
            for i in range(0, len(all_cells), batch_size):
                insert_raw_cells_batch(conn, all_cells[i:i + batch_size], commit=False)

            conn.commit()
            _emit(progress_callback, "Done", "Import complete.")
            return stats

        survey_path = data_dir / SURVEY_FILE
        if not survey_path.exists():
            raise FileNotFoundError(f"Survey workbook not found: {survey_path}")

        # ── Step 1: Parse base sheet (All Equip) ────────────────────────────
        _emit(progress_callback, "Parsing", "Reading All Equip sheet...")
        base_records, base_issues = parse_base_sheet(master_path)
        all_issues.extend(base_issues)
        stats["base_records"] = len(base_records)

        # ── Step 2: Apply overlay sheets ────────────────────────────────────
        _emit(progress_callback, "Overlays", "Applying calibration, repair, scrapped sheets...")
        base_records, overlay_issues = parse_overlay_sheets(master_path, base_records)
        all_issues.extend(overlay_issues)
        stats["overlay_issues"] = len(overlay_issues)

        # ── Step 3: Parse survey ────────────────────────────────────────────
        _emit(progress_callback, "Survey", "Parsing survey workbook...")
        survey_rows, survey_issues = parse_survey(survey_path)
        all_issues.extend(survey_issues)

        # ── Step 4: Match survey rows to base records ───────────────────────
        _emit(progress_callback, "Matching", "Matching survey to base inventory...")
        _match_survey(base_records, survey_rows, all_issues, stats)

        # ── Step 5: Detect duplicates ───────────────────────────────────────
        _emit(progress_callback, "Dedup", "Checking for duplicates...")
        _detect_duplicates(base_records, all_issues)

        # ── Step 6: Insert equipment into database ──────────────────────────
        _emit(progress_callback, "Saving", "Writing equipment records to database...")
        for eq in base_records:
            insert_equipment(conn, eq, commit=False)

        # ── Step 7: Insert import issues ────────────────────────────────────
        _emit(progress_callback, "Issues", "Recording import issues...")
        for issue in all_issues:
            insert_import_issue(conn, issue, commit=False)
        stats["total_issues"] = len(all_issues)

        # ── Step 8: Index raw cells (both workbooks) ────────────────────────
        _emit(progress_callback, "Indexing", "Indexing master workbook cells...")
        master_cells = index_all_raw_cells(master_path)

        _emit(progress_callback, "Indexing", "Indexing survey workbook cells...")
        survey_cells = index_survey_raw_cells(survey_path)

        all_cells = master_cells + survey_cells
        stats["total_raw_cells"] = len(all_cells)

        _emit(progress_callback, "Indexing", f"Writing {len(all_cells)} cells to search index...")
        batch_size = 5000
        for i in range(0, len(all_cells), batch_size):
            insert_raw_cells_batch(conn, all_cells[i:i + batch_size], commit=False)

        conn.commit()
        _emit(progress_callback, "Done", "Import complete.")
        return stats
    except Exception:
        if conn.in_transaction:
            conn.rollback()
        raise
    finally:
        conn.close()


def run_merge_import(data_dir: Path, db_path: Path | None = None,
                     progress_callback=None) -> dict:
    """Parse the current Excel files and merge them into the existing database."""
    master_path = data_dir / MASTER_FILE
    if not master_path.exists():
        raise FileNotFoundError(f"Master workbook not found: {master_path}")

    survey_path = None
    if _import_profile() != "me_single_workbook":
        survey_path = data_dir / SURVEY_FILE
        if not survey_path.exists():
            raise FileNotFoundError(f"Survey workbook not found: {survey_path}")
    conn = get_connection(db_path)

    stats = {
        "parsed_records": 0,
        "added_records": 0,
        "matched_records": 0,
        "updated_records": 0,
        "merge_conflicts": 0,
        "survey_matched": 0,
        "survey_unmatched": 0,
        "total_raw_cells": 0,
        "total_issues": 0,
    }

    all_issues: list[ImportIssue] = []

    try:
        create_tables(conn)

        if _import_profile() == "me_single_workbook":
            _emit(progress_callback, "Parsing", "Reading ME inventory workbook...")
            imported_records, base_issues = parse_me_workbook(master_path)
            all_issues.extend(base_issues)
            stats["parsed_records"] = len(imported_records)

            combined_records = get_all_equipment(conn)
            updated_records: dict[int, Equipment] = {}

            _emit(progress_callback, "Merging", "Merging ME workbook into the current database...")
            new_records = _merge_imported_records(
                combined_records,
                imported_records,
                all_issues,
                stats,
                updated_records,
            )
            stats["updated_records"] = len(updated_records)

            _emit(progress_callback, "Dedup", "Checking for duplicates in the merged inventory...")
            _detect_duplicates(combined_records, all_issues)

            _emit(progress_callback, "Indexing", "Indexing ME workbook cells...")
            all_cells = index_me_raw_cells(master_path)
            stats["total_raw_cells"] = len(all_cells)

            conn.execute("BEGIN")
            _delete_import_artifacts(conn, (MASTER_FILE,))

            _emit(progress_callback, "Saving", "Writing merged inventory records to database...")
            for eq in new_records:
                insert_equipment(conn, eq, commit=False)
            for eq in updated_records.values():
                update_equipment(conn, eq, commit=False)

            _emit(progress_callback, "Issues", "Recording import issues...")
            for issue in all_issues:
                insert_import_issue(conn, issue, commit=False)
            stats["total_issues"] = len(all_issues)

            batch_size = 5000
            for i in range(0, len(all_cells), batch_size):
                insert_raw_cells_batch(conn, all_cells[i:i + batch_size], commit=False)

            conn.commit()
            _emit(progress_callback, "Done", "Excel merge import complete.")
            return stats

        _emit(progress_callback, "Parsing", "Reading All Equip sheet...")
        imported_records, base_issues = parse_base_sheet(master_path)
        all_issues.extend(base_issues)
        stats["parsed_records"] = len(imported_records)

        _emit(progress_callback, "Overlays", "Applying calibration, repair, scrapped sheets...")
        imported_records, overlay_issues = parse_overlay_sheets(master_path, imported_records)
        all_issues.extend(overlay_issues)

        _emit(progress_callback, "Survey", "Parsing survey workbook...")
        survey_rows, survey_issues = parse_survey(survey_path)
        all_issues.extend(survey_issues)

        combined_records = get_all_equipment(conn)
        updated_records: dict[int, Equipment] = {}

        _emit(progress_callback, "Merging", "Merging imported equipment into the current database...")
        new_records = _merge_imported_records(
            combined_records,
            imported_records,
            all_issues,
            stats,
            updated_records,
        )
        stats["updated_records"] = len(updated_records)

        _emit(progress_callback, "Matching", "Matching survey to the combined inventory...")
        _match_survey(combined_records, survey_rows, all_issues, stats, updated_records)
        stats["updated_records"] = len(updated_records)

        _emit(progress_callback, "Dedup", "Checking for duplicates in the merged inventory...")
        _detect_duplicates(combined_records, all_issues)

        _emit(progress_callback, "Indexing", "Indexing master workbook cells...")
        master_cells = index_all_raw_cells(master_path)

        _emit(progress_callback, "Indexing", "Indexing survey workbook cells...")
        survey_cells = index_survey_raw_cells(survey_path)

        all_cells = master_cells + survey_cells
        stats["total_raw_cells"] = len(all_cells)

        conn.execute("BEGIN")
        _delete_import_artifacts(conn, (MASTER_FILE, SURVEY_FILE))

        _emit(progress_callback, "Saving", "Writing merged equipment records to database...")
        for eq in new_records:
            insert_equipment(conn, eq, commit=False)
        for eq in updated_records.values():
            update_equipment(conn, eq, commit=False)

        _emit(progress_callback, "Issues", "Recording import issues...")
        for issue in all_issues:
            insert_import_issue(conn, issue, commit=False)
        stats["total_issues"] = len(all_issues)

        _emit(progress_callback, "Indexing", f"Writing {len(all_cells)} cells to search index...")
        batch_size = 5000
        for i in range(0, len(all_cells), batch_size):
            insert_raw_cells_batch(conn, all_cells[i:i + batch_size], commit=False)

        conn.commit()
        _emit(progress_callback, "Done", "Excel merge import complete.")
        return stats
    except Exception:
        if conn.in_transaction:
            conn.rollback()
        raise
    finally:
        conn.close()


def _match_survey(base_records: list[Equipment],
                  survey_rows: list[dict],
                  issues: list[ImportIssue],
                  stats: dict,
                  updated_records: dict[int, Equipment] | None = None) -> None:
    """Match survey rows to base equipment records.

    Updates matched records with blue dot and age info.
    Creates import issues for unmatched survey rows.
    """
    by_asset, by_serial, by_import_key = build_equipment_indexes(base_records)

    for srow in survey_rows:
        asset = srow.get("asset_number", "").strip()
        serial = srow.get("serial_number", "").strip()
        source_row = srow.get("source_row", 0)

        match = resolve_equipment_match(by_asset, by_serial, by_import_key, asset, serial)
        if match.record is not None:
            matched = match.record
            stats["survey_matched"] = stats.get("survey_matched", 0) + 1
            matched.verified_in_survey = True

            # Set blue dot reference
            bd = srow.get("blue_dot", "")
            if bd and not is_placeholder(bd):
                matched.blue_dot_ref = bd

            # Age hint from survey
            how_old = srow.get("how_old", "").strip()
            if how_old and not is_placeholder(how_old):
                try:
                    age_val = float(how_old.replace("+", "").strip())
                    if matched.estimated_age_years is None:
                        matched.estimated_age_years = age_val
                        matched.age_basis = "survey"
                except ValueError:
                    pass

            # Update location from survey if base has none
            loc = srow.get("location", "")
            if loc and not is_placeholder(loc) and not matched.location:
                matched.location = loc

            # If survey section indicates non-working
            if srow.get("section") == "non_working":
                matched.working_status = "not_working"

            # Track survey source ref
            _add_unique_source_ref(matched, SURVEY_FILE, "Sheet1", source_row)
            if updated_records is not None and matched.record_id is not None:
                updated_records[matched.record_id] = matched

        else:
            stats["survey_unmatched"] = stats.get("survey_unmatched", 0) + 1
            summary = f"Survey row {source_row}: {match.summary}"
            context = " ".join(
                part for part in (srow.get("manufacturer", ""), srow.get("model", ""))
                if part
            ).strip()
            if context:
                summary = f"{summary} ({context})"
            issues.append(ImportIssue(
                issue_type=match.status,
                source_file=SURVEY_FILE,
                source_sheet="Sheet1",
                source_row=source_row,
                asset_number=asset,
                serial_number=serial,
                summary=summary,
                raw_data=json.dumps(srow),
            ))


def _detect_duplicates(records: list[Equipment],
                       issues: list[ImportIssue]) -> None:
    """Flag records that share the same asset_number or serial_number."""
    _detect_duplicate_field(records, issues, "asset_number", "asset number")
    _detect_duplicate_field(records, issues, "serial_number", "serial number")


def _emit(callback, step: str, detail: str) -> None:
    """Emit a progress update if callback is provided."""
    if callback:
        callback(step, detail)


def _detect_duplicate_field(
    records: list[Equipment],
    issues: list[ImportIssue],
    field_name: str,
    label: str,
) -> None:
    """Create issues for every record participating in a duplicate identifier group."""
    seen: dict[str, list[Equipment]] = {}

    for eq in records:
        value = getattr(eq, field_name, "").strip()
        if not value:
            continue
        key = value.upper()
        if key not in seen:
            seen[key] = []
        seen[key].append(eq)

    for duplicates in seen.values():
        if len(duplicates) < 2:
            continue
        for eq in duplicates:
            value = getattr(eq, field_name, "")
            issues.append(ImportIssue(
                issue_type="duplicate",
                source_file=MASTER_FILE,
                source_sheet="All Equip",
                source_row=_source_row_from_refs(eq.source_refs),
                asset_number=eq.asset_number,
                serial_number=eq.serial_number,
                summary=f"Duplicate {label} '{value}' ({eq.manufacturer} {eq.model})",
            ))


def _source_row_from_refs(source_refs: str) -> int:
    """Return the first All Equip source row recorded for an equipment record."""
    return Equipment(source_refs=source_refs).first_source_row("All Equip")


def _merge_imported_records(
    combined_records: list[Equipment],
    imported_records: list[Equipment],
    issues: list[ImportIssue],
    stats: dict,
    updated_records: dict[int, Equipment],
) -> list[Equipment]:
    """Merge imported equipment rows into the existing in-memory record set."""
    by_asset, by_serial, by_import_key = build_equipment_indexes(combined_records)
    new_records: list[Equipment] = []

    for imported in imported_records:
        match = resolve_equipment_match(
            by_asset,
            by_serial,
            by_import_key,
            imported.asset_number,
            imported.serial_number,
            imported.primary_import_key(),
        )
        if match.record is None:
            if match.status == "unmatched":
                combined_records.append(imported)
                new_records.append(imported)
                _index_equipment_record(by_asset, by_serial, by_import_key, imported)
                stats["added_records"] = stats.get("added_records", 0) + 1
                continue

            source_row = _source_row_from_refs(imported.source_refs)
            stats["merge_conflicts"] = stats.get("merge_conflicts", 0) + 1
            issues.append(ImportIssue(
                issue_type=match.status,
                source_file=MASTER_FILE,
                source_sheet="All Equip",
                source_row=source_row,
                asset_number=imported.asset_number,
                serial_number=imported.serial_number,
                summary=f"All Equip row {source_row} {match.summary}",
                raw_data=_equipment_to_issue_payload(imported),
            ))
            continue

        stats["matched_records"] = stats.get("matched_records", 0) + 1
        if _merge_equipment(existing=match.record, incoming=imported) and match.record.record_id is not None:
            updated_records[match.record.record_id] = match.record

    return new_records


def _merge_equipment(existing: Equipment, incoming: Equipment) -> bool:
    """Merge an imported record into an existing one without overwriting newer/current data."""
    changed = False

    changed |= _fill_text_field(existing, incoming, "asset_number")
    changed |= _fill_text_field(existing, incoming, "serial_number")
    changed |= _fill_text_field(existing, incoming, "manufacturer")
    changed |= _fill_text_field(existing, incoming, "manufacturer_raw")
    changed |= _fill_text_field(existing, incoming, "model")
    changed |= _fill_text_field(existing, incoming, "description")
    changed |= _fill_text_field(existing, incoming, "location")
    changed |= _fill_text_field(existing, incoming, "assigned_to")
    changed |= _fill_text_field(existing, incoming, "condition")
    changed |= _fill_text_field(existing, incoming, "calibration_vendor")
    changed |= _fill_text_field(existing, incoming, "rental_vendor")
    changed |= _fill_text_field(existing, incoming, "blue_dot_ref")
    changed |= _fill_text_field(existing, incoming, "acquired_date")

    changed |= _fill_numeric_field(existing, incoming, "qty")
    changed |= _fill_numeric_field(existing, incoming, "rental_cost_monthly")
    changed |= _fill_numeric_field(existing, incoming, "calibration_cost")
    if _fill_numeric_field(existing, incoming, "estimated_age_years"):
        changed = True
        if incoming.age_basis and incoming.age_basis != "unknown" and existing.age_basis == "unknown":
            existing.age_basis = incoming.age_basis

    changed |= _prefer_later_date(existing, incoming, "last_calibration_date")
    changed |= _prefer_later_date(existing, incoming, "calibration_due_date")
    changed |= _fill_status_field(existing, incoming, "calibration_status", blank_values={"", "unknown"})
    changed |= _fill_status_field(existing, incoming, "working_status", blank_values={"", "unknown"})
    changed |= _fill_status_field(existing, incoming, "ownership_type", blank_values={"", "unknown"})
    changed |= _merge_notes(existing, incoming)

    if incoming.verified_in_survey and not existing.verified_in_survey:
        existing.verified_in_survey = True
        changed = True

    if _merge_source_refs(existing, incoming):
        changed = True

    return changed


def _fill_text_field(existing: Equipment, incoming: Equipment, field_name: str) -> bool:
    """Fill a text field only when the existing record has no meaningful value."""
    incoming_value = getattr(incoming, field_name, "")
    existing_value = getattr(existing, field_name, "")
    if _has_meaningful_text(incoming_value) and not _has_meaningful_text(existing_value):
        setattr(existing, field_name, incoming_value.strip())
        return True
    return False


def _fill_numeric_field(existing: Equipment, incoming: Equipment, field_name: str) -> bool:
    """Fill a numeric field only when the existing record has no value yet."""
    incoming_value = getattr(incoming, field_name, None)
    existing_value = getattr(existing, field_name, None)
    if incoming_value is not None and existing_value is None:
        setattr(existing, field_name, incoming_value)
        return True
    return False


def _prefer_later_date(existing: Equipment, incoming: Equipment, field_name: str) -> bool:
    """Keep the latest non-empty ISO date between two records."""
    incoming_value = getattr(incoming, field_name, "")
    existing_value = getattr(existing, field_name, "")
    if not incoming_value:
        return False
    if not existing_value or incoming_value > existing_value:
        setattr(existing, field_name, incoming_value)
        return True
    return False


def _fill_status_field(
    existing: Equipment,
    incoming: Equipment,
    field_name: str,
    blank_values: set[str],
) -> bool:
    """Fill a status field only when the existing value is blank-like."""
    incoming_value = getattr(incoming, field_name, "")
    existing_value = getattr(existing, field_name, "")
    if incoming_value and incoming_value not in blank_values and existing_value in blank_values:
        setattr(existing, field_name, incoming_value)
        return True
    return False


def _merge_notes(existing: Equipment, incoming: Equipment) -> bool:
    """Append imported notes only when they add new information."""
    if not _has_meaningful_text(incoming.notes):
        return False
    if not _has_meaningful_text(existing.notes):
        existing.notes = incoming.notes.strip()
        return True
    if incoming.notes.strip() in existing.notes:
        return False
    existing.notes = f"{existing.notes} | {incoming.notes.strip()}".strip(" | ")
    return True


def _merge_source_refs(existing: Equipment, incoming: Equipment) -> bool:
    """Union source refs while preserving order and avoiding duplicates."""
    existing_refs = existing.parsed_source_refs()
    seen = {
        (ref.get("file", ""), ref.get("sheet", ""), str(ref.get("row", "")))
        for ref in existing_refs
    }
    changed = False
    for ref in incoming.parsed_source_refs():
        key = (ref.get("file", ""), ref.get("sheet", ""), str(ref.get("row", "")))
        if key in seen:
            continue
        existing_refs.append(ref)
        seen.add(key)
        changed = True
    if changed:
        existing.set_parsed_source_refs(existing_refs)
    return changed


def _add_unique_source_ref(eq: Equipment, file: str, sheet: str, row: int) -> bool:
    """Append a source reference only when it is not already present."""
    refs = eq.parsed_source_refs()
    key = (file, sheet, str(row))
    for ref in refs:
        existing_key = (
            ref.get("file", ""),
            ref.get("sheet", ""),
            str(ref.get("row", "")),
        )
        if existing_key == key:
            return False
    refs.append({"file": file, "sheet": sheet, "row": row})
    eq.set_parsed_source_refs(refs)
    return True


def _index_equipment_record(
    by_asset: dict[str, list[Equipment]],
    by_serial: dict[str, list[Equipment]],
    by_import_key: dict[str, list[Equipment]],
    eq: Equipment,
) -> None:
    """Add a single equipment record to the existing match indexes."""
    asset_key = eq.asset_number.strip().upper()
    serial_key = eq.serial_number.strip().upper()
    import_key = eq.primary_import_key().strip().upper()
    if asset_key:
        by_asset.setdefault(asset_key, []).append(eq)
    if serial_key:
        by_serial.setdefault(serial_key, []).append(eq)
    if import_key:
        by_import_key.setdefault(import_key, []).append(eq)


def _equipment_to_issue_payload(eq: Equipment) -> str:
    """Serialize a subset of an equipment record for issue tracking."""
    return json.dumps({
        "asset_number": eq.asset_number,
        "serial_number": eq.serial_number,
        "manufacturer": eq.manufacturer_raw or eq.manufacturer,
        "model": eq.model,
        "description": eq.description,
        "location": eq.location,
    })


def _has_meaningful_text(value: str) -> bool:
    """Return whether a string contains a non-placeholder value."""
    return bool(value and value.strip() and not is_placeholder(value))


def _delete_import_artifacts(conn, source_files: tuple[str, ...]) -> None:
    """Replace prior issues and raw-cell indexes for the same workbook names."""
    placeholders = ", ".join("?" for _ in source_files)
    conn.execute(
        f"DELETE FROM raw_cells WHERE source_file IN ({placeholders})",
        source_files,
    )
    conn.execute(
        f"DELETE FROM import_issues WHERE source_file IN ({placeholders})",
        source_files,
    )


def _import_profile() -> str:
    """Return the active workbook import profile for the current app."""
    return getattr(APP_CONFIG, "import_profile", "te_dual_workbook")

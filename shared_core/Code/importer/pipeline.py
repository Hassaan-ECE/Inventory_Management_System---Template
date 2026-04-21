"""Compatibility facade for full/merge import pipeline orchestration."""

from __future__ import annotations

from pathlib import Path

from app_config import APP_CONFIG
from Code.importer.pipeline_full import (
    _emit,
    _import_profile,
    _resolve_target_db_path,
    run_full_import as _run_full_import,
    run_full_import_to_db as _run_full_import_to_db,
)
from Code.importer.pipeline_merge import (
    run_merge_import as _run_merge_import,
    run_merge_import_to_db as _run_merge_import_to_db,
)
from Code.importer.pipeline_merge_helpers import (
    _add_unique_source_ref,
    _delete_import_artifacts,
    _detect_duplicate_field,
    _detect_duplicates,
    _equipment_to_issue_payload,
    _fill_numeric_field,
    _fill_status_field,
    _fill_text_field,
    _has_meaningful_text,
    _index_equipment_record,
    _match_survey,
    _merge_equipment,
    _merge_imported_records,
    _merge_notes,
    _merge_source_refs,
    _prefer_later_date,
    _source_row_from_refs,
)


def _profile_strategy() -> str:
    profile = getattr(APP_CONFIG, "import_profile", "te_dual_workbook")
    return "single_workbook" if profile == "me_single_workbook" else "dual_workbook"


def run_full_import(
    data_dir: Path,
    db_path: Path | None = None,
    progress_callback=None,
    *,
    target_db_path: Path | str | None = None,
    use_wal: bool = True,
) -> dict:
    """Run the complete full-import flow for the active profile strategy."""
    return _run_full_import(
        data_dir=data_dir,
        db_path=db_path,
        progress_callback=progress_callback,
        target_db_path=target_db_path,
        use_wal=use_wal,
        strategy=_profile_strategy(),
    )


def run_merge_import(
    data_dir: Path,
    db_path: Path | None = None,
    progress_callback=None,
    *,
    target_db_path: Path | str | None = None,
    use_wal: bool = True,
) -> dict:
    """Run the merge-import flow for the active profile strategy."""
    return _run_merge_import(
        data_dir=data_dir,
        db_path=db_path,
        progress_callback=progress_callback,
        target_db_path=target_db_path,
        use_wal=use_wal,
        strategy=_profile_strategy(),
    )


def run_full_import_to_db(
    data_dir: Path,
    target_db_path: Path | str,
    progress_callback=None,
    *,
    use_wal: bool = False,
) -> dict:
    """Run a full import into an explicit database path."""
    return _run_full_import_to_db(
        data_dir=data_dir,
        target_db_path=target_db_path,
        progress_callback=progress_callback,
        use_wal=use_wal,
        strategy=_profile_strategy(),
    )


def run_merge_import_to_db(
    data_dir: Path,
    target_db_path: Path | str,
    progress_callback=None,
    *,
    use_wal: bool = False,
) -> dict:
    """Run a merge import into an explicit database path."""
    return _run_merge_import_to_db(
        data_dir=data_dir,
        target_db_path=target_db_path,
        progress_callback=progress_callback,
        use_wal=use_wal,
        strategy=_profile_strategy(),
    )


__all__ = [
    "_add_unique_source_ref",
    "_delete_import_artifacts",
    "_detect_duplicate_field",
    "_detect_duplicates",
    "_emit",
    "_equipment_to_issue_payload",
    "_fill_numeric_field",
    "_fill_status_field",
    "_fill_text_field",
    "_has_meaningful_text",
    "_import_profile",
    "_index_equipment_record",
    "_match_survey",
    "_merge_equipment",
    "_merge_imported_records",
    "_merge_notes",
    "_merge_source_refs",
    "_prefer_later_date",
    "_profile_strategy",
    "_resolve_target_db_path",
    "_source_row_from_refs",
    "run_full_import",
    "run_full_import_to_db",
    "run_merge_import",
    "run_merge_import_to_db",
]
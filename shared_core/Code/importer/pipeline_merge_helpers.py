"""Merge/dedupe/match helper functions used by pipeline entry points."""

from __future__ import annotations

from Code.importer._pipeline_impl import (
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

__all__ = [
    "_add_unique_source_ref",
    "_delete_import_artifacts",
    "_detect_duplicate_field",
    "_detect_duplicates",
    "_equipment_to_issue_payload",
    "_fill_numeric_field",
    "_fill_status_field",
    "_fill_text_field",
    "_has_meaningful_text",
    "_index_equipment_record",
    "_match_survey",
    "_merge_equipment",
    "_merge_imported_records",
    "_merge_notes",
    "_merge_source_refs",
    "_prefer_later_date",
    "_source_row_from_refs",
]

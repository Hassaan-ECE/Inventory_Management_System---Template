"""Equipment CRUD, search, and summary operations."""

from __future__ import annotations

from Code.db._database_impl import (
    delete_equipment,
    get_all_equipment,
    get_distinct_equipment_values,
    get_equipment_by_id,
    get_equipment_by_uuid,
    get_equipment_stats,
    insert_equipment,
    search_equipment,
    update_equipment,
)

__all__ = [
    "delete_equipment",
    "get_all_equipment",
    "get_distinct_equipment_values",
    "get_equipment_by_id",
    "get_equipment_by_uuid",
    "get_equipment_stats",
    "insert_equipment",
    "search_equipment",
    "update_equipment",
]

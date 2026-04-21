"""Characterization tests for equipment CRUD, search, and stats behavior."""

from __future__ import annotations

from pathlib import Path

import pytest

from Code.db.database import (
    create_tables,
    delete_equipment,
    get_connection,
    get_distinct_equipment_values,
    get_equipment_by_uuid,
    get_equipment_stats,
    insert_equipment,
    search_equipment,
    update_equipment,
)
from Code.db.models import Equipment


@pytest.fixture
def db_conn(tmp_path: Path):
    db_path = tmp_path / "characterization.db"
    conn = get_connection(db_path)
    create_tables(conn)
    try:
        yield conn
    finally:
        conn.close()


def _equipment(*, asset: str, serial: str, manufacturer: str, model: str, archived: bool = False) -> Equipment:
    return Equipment(
        record_uuid=f"{asset}-{serial}".lower(),
        asset_number=asset,
        serial_number=serial,
        manufacturer=manufacturer,
        model=model,
        description=f"{manufacturer} {model}",
        location="Lab A",
        lifecycle_status="active",
        working_status="working",
        calibration_status="calibrated",
        is_archived=archived,
    )


def test_crud_and_search_behavior_is_stable(db_conn) -> None:
    first = _equipment(asset="A-100", serial="S-100", manufacturer="Fluke", model="87V")
    second = _equipment(asset="A-200", serial="S-200", manufacturer="Keysight", model="34461A", archived=True)
    first.record_id = insert_equipment(db_conn, first)
    second.record_id = insert_equipment(db_conn, second)

    live_results = search_equipment(db_conn, "fluke")
    assert [row.record_uuid for row in live_results] == [first.record_uuid]

    archived_results = search_equipment(db_conn, "keysight", archived="archived")
    assert [row.record_uuid for row in archived_results] == [second.record_uuid]

    second.description = "Archived benchtop meter"
    second.record_id = get_equipment_by_uuid(db_conn, second.record_uuid).record_id
    update_equipment(db_conn, second)
    updated = get_equipment_by_uuid(db_conn, second.record_uuid)
    assert updated is not None
    assert updated.description == "Archived benchtop meter"

    delete_equipment(db_conn, first.record_id)
    assert get_equipment_by_uuid(db_conn, first.record_uuid) is None


def test_stats_and_distinct_values_are_stable(db_conn) -> None:
    insert_equipment(db_conn, _equipment(asset="A-101", serial="S-101", manufacturer="Fluke", model="179"))
    insert_equipment(db_conn, _equipment(asset="A-102", serial="S-102", manufacturer="Tektronix", model="TDS"))
    insert_equipment(
        db_conn,
        _equipment(asset="A-103", serial="S-103", manufacturer="Tektronix", model="MDO", archived=True),
    )

    stats = get_equipment_stats(db_conn, archived="all")
    assert stats["total"] == 3
    assert stats["archived"] == 1
    assert stats["calibrated"] == 3

    manufacturers = get_distinct_equipment_values(db_conn, "manufacturer")
    assert manufacturers == ["Fluke", "Tektronix"]

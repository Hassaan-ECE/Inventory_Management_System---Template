"""Characterization tests for shared-first sync behavior paths."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from types import SimpleNamespace

import pytest

from Code.db.database import (
    create_tables,
    get_connection,
    get_equipment_by_uuid,
    insert_equipment,
    set_sync_state,
)
from Code.db.models import Equipment
from Code.sync import service
import Code.sync._service_impl as service_impl


def _configure_shared_sync(monkeypatch: pytest.MonkeyPatch, *, shared_db_filename: str = "shared_inventory.db") -> None:
    config = SimpleNamespace(
        enable_shared_sync=True,
        shared_db_filename=shared_db_filename,
        display_name="Lab Inventory",
        auto_sync_interval_ms=300000,
    )
    monkeypatch.setattr(
        service,
        "APP_CONFIG",
        config,
        raising=False,
    )
    monkeypatch.setattr(
        service_impl,
        "APP_CONFIG",
        config,
        raising=False,
    )


def _shared_db_path(root: Path, filename: str) -> Path:
    shared_dir = root / "shared"
    shared_dir.mkdir(parents=True, exist_ok=True)
    return shared_dir / filename


def test_sync_local_from_shared_happy_path_refreshes_cache(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _configure_shared_sync(monkeypatch)
    root = tmp_path / "network_root"
    local_db = tmp_path / "local.db"
    shared_db = _shared_db_path(root, "shared_inventory.db")

    shared_conn = get_connection(shared_db, use_wal=False)
    try:
        create_tables(shared_conn)
        insert_equipment(
            shared_conn,
            Equipment(
                record_uuid="shared-1",
                asset_number="SHARED-001",
                serial_number="S-001",
                manufacturer="Fluke",
                model="87V",
            ),
        )
        set_sync_state(
            shared_conn,
            revision="3",
            equipment_snapshot_hash="",
            import_issue_snapshot_hash="",
            global_mutation_at="",
        )
    finally:
        shared_conn.close()

    result = service.sync_local_from_shared(local_db, override_root=root)
    assert result.enabled is True
    assert result.shared_available is True
    assert result.local_revision == "3"

    local_conn = get_connection(local_db)
    try:
        assert get_equipment_by_uuid(local_conn, "shared-1") is not None
    finally:
        local_conn.close()


def test_sync_unavailable_path_reports_view_only_mode(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _configure_shared_sync(monkeypatch)
    local_db = tmp_path / "local.db"
    missing_root = tmp_path / "missing_network_root"

    result = service.sync_local_from_shared(local_db, override_root=missing_root)
    assert result.enabled is True
    assert result.shared_available is False
    assert "Viewing local cache only" in result.message

    revision = service.check_revision(local_db, override_root=missing_root)
    assert revision.enabled is True
    assert revision.shared_available is False
    assert "Viewing local cache only" in revision.message


def test_sync_busy_path_surfaces_non_blocking_busy_status(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _configure_shared_sync(monkeypatch)
    root = tmp_path / "network_root"
    root.mkdir(parents=True, exist_ok=True)
    local_db = tmp_path / "local.db"

    def _busy_connection(_path: Path):
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr(service_impl, "_shared_connection", _busy_connection)
    result = service.sync_local_from_shared(local_db, override_root=root)
    assert result.enabled is True
    assert result.shared_available is True
    assert result.busy is True
    assert "busy" in result.message.lower()


def test_shared_mutation_refreshes_local_cache(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _configure_shared_sync(monkeypatch)
    root = tmp_path / "network_root"
    local_db = tmp_path / "local.db"
    shared_db = _shared_db_path(root, "shared_inventory.db")

    shared_conn = get_connection(shared_db, use_wal=False)
    try:
        create_tables(shared_conn)
        set_sync_state(
            shared_conn,
            revision="1",
            equipment_snapshot_hash="",
            import_issue_snapshot_hash="",
            global_mutation_at="",
        )
    finally:
        shared_conn.close()

    first_sync = service.sync_local_from_shared(local_db, override_root=root)
    assert first_sync.shared_available is True

    created = service.create_equipment(
        local_db,
        Equipment(
            record_uuid="created-1",
            asset_number="NEW-001",
            serial_number="NEW-S-001",
            manufacturer="Keysight",
            model="34461A",
        ),
        override_root=root,
    )
    assert created.record_uuid == "created-1"

    local_conn = get_connection(local_db)
    try:
        assert get_equipment_by_uuid(local_conn, "created-1") is not None
    finally:
        local_conn.close()

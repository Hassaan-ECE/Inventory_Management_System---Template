"""Characterization tests for main-window core action routing."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

import Code.gui.main_window as main_window_module
from Code.db.database import create_tables, get_connection, get_equipment_by_uuid
from Code.db.models import Equipment
from Code.gui.main_window import MainWindow


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication([])
    return app


@pytest.fixture
def db_conn(tmp_path: Path):
    db_path = tmp_path / "window.db"
    conn = get_connection(db_path)
    create_tables(conn)
    try:
        yield conn
    finally:
        conn.close()


def test_local_mode_core_actions_mutate_local_db(monkeypatch: pytest.MonkeyPatch, qapp, db_conn) -> None:
    monkeypatch.setattr(main_window_module, "shared_sync_enabled", lambda: False)
    window = MainWindow(db_conn)
    try:
        eq = Equipment(
            record_uuid="mw-local-1",
            asset_number="MW-001",
            serial_number="MW-S-001",
            manufacturer="Fluke",
            model="117",
        )

        window._submit_create_equipment(eq)
        created = get_equipment_by_uuid(db_conn, "mw-local-1")
        assert created is not None

        window._submit_archive_change("mw-local-1", True)
        archived = get_equipment_by_uuid(db_conn, "mw-local-1")
        assert archived is not None
        assert archived.is_archived is True

        window._submit_toggle_verified("mw-local-1")
        verified = get_equipment_by_uuid(db_conn, "mw-local-1")
        assert verified is not None
        assert verified.verified_in_survey is True

        window._submit_delete_record(verified.record_id, verified.record_uuid)
        assert get_equipment_by_uuid(db_conn, "mw-local-1") is None
    finally:
        window.close()


def test_shared_mode_routes_create_to_shared_service(monkeypatch: pytest.MonkeyPatch, qapp, db_conn) -> None:
    monkeypatch.setattr(main_window_module, "shared_sync_enabled", lambda: True)
    monkeypatch.setattr(MainWindow, "_setup_sync_worker", lambda self: None)
    monkeypatch.setattr(MainWindow, "_refresh_shared_watch_paths", lambda self: None)

    calls: list[str] = []

    def _fake_create(_conn, equipment):
        calls.append(equipment.record_uuid)
        return equipment

    monkeypatch.setattr(main_window_module, "create_equipment_shared", _fake_create)

    window = MainWindow(db_conn)
    try:
        window._shared_actions_available = True
        window._submit_create_equipment(
            Equipment(
                record_uuid="mw-shared-1",
                asset_number="MW-SHARED-001",
                serial_number="MW-SHARED-S-001",
                manufacturer="Keysight",
                model="34465A",
            )
        )
        assert calls == ["mw-shared-1"]
    finally:
        window.close()

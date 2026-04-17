"""Regression tests for the ME shared-sync and update foundation."""

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from app_config import APP_CONFIG
from Code.db.database import create_tables, get_all_equipment, get_connection, insert_equipment, update_equipment
from Code.db.models import Equipment
from Code.sync.service import check_for_update, sync_interval_ms, sync_local_with_shared


class SharedSyncTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name) / "shared_root"
        self.root.mkdir(parents=True, exist_ok=True)
        self.local_path = Path(self.temp_dir.name) / "local.db"
        self.local_conn = get_connection(self.local_path)
        create_tables(self.local_conn)

    def tearDown(self) -> None:
        self.local_conn.close()
        self.temp_dir.cleanup()

    def _shared_db_path(self) -> Path:
        return self.root / "shared" / APP_CONFIG.shared_db_filename

    def _open_shared_conn(self):
        shared_path = self._shared_db_path()
        shared_path.parent.mkdir(parents=True, exist_ok=True)
        conn = get_connection(shared_path, use_wal=False)
        create_tables(conn)
        return conn

    def test_check_for_update_reads_newer_relative_installer_manifest(self) -> None:
        installer_path = self.root / "releases" / "1.0.1" / "ME_Lab_Inventory_Setup.exe"
        installer_path.parent.mkdir(parents=True, exist_ok=True)
        installer_path.write_text("stub installer", encoding="utf-8")

        manifest_path = self.root / APP_CONFIG.release_manifest_filename
        manifest_path.write_text(
            json.dumps(
                {
                    "version": "1.0.1",
                    "installer_path": str(installer_path.relative_to(self.root)),
                    "published_at": "2026-04-16 09:00:00",
                    "notes": "Shared sync improvements",
                }
            ),
            encoding="utf-8",
        )

        info = check_for_update(override_root=self.root)

        self.assertIsNotNone(info)
        self.assertEqual(info.version, "1.0.1")
        self.assertEqual(info.installer_path, installer_path)
        self.assertEqual(info.notes, "Shared sync improvements")

    def test_sync_interval_ms_allows_shorter_configured_polling(self) -> None:
        with patch(
            "Code.sync.service.APP_CONFIG",
            SimpleNamespace(auto_sync_interval_ms=10000),
        ):
            self.assertEqual(sync_interval_ms(), 10000)

        with patch(
            "Code.sync.service.APP_CONFIG",
            SimpleNamespace(auto_sync_interval_ms=1000),
        ):
            self.assertEqual(sync_interval_ms(), 5000)

    def test_sync_initializes_local_database_from_shared_snapshot(self) -> None:
        shared_conn = self._open_shared_conn()
        try:
            insert_equipment(
                shared_conn,
                Equipment(
                    asset_number="ME-100",
                    manufacturer="Fluke",
                    manufacturer_raw="Fluke",
                    description="Shared multimeter",
                ),
            )
        finally:
            shared_conn.close()

        result = sync_local_with_shared(self.local_conn, override_root=self.root)
        rows = get_all_equipment(self.local_conn, archived="all")

        self.assertEqual(result.initialized, "local")
        self.assertEqual(result.pulled, 1)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].asset_number, "ME-100")
        self.assertTrue(rows[0].record_uuid)
        self.assertEqual(
            self.local_conn.execute("SELECT COUNT(*) FROM record_sync_state").fetchone()[0],
            1,
        )

    def test_sync_initializes_shared_database_from_local_snapshot(self) -> None:
        insert_equipment(
            self.local_conn,
            Equipment(
                asset_number="ME-200",
                manufacturer="Mitutoyo",
                manufacturer_raw="Mitutoyo",
                description="Local caliper",
            ),
        )

        result = sync_local_with_shared(self.local_conn, override_root=self.root)

        shared_conn = self._open_shared_conn()
        try:
            rows = get_all_equipment(shared_conn, archived="all")
        finally:
            shared_conn.close()

        self.assertEqual(result.initialized, "shared")
        self.assertEqual(result.pushed, 1)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].asset_number, "ME-200")
        self.assertTrue(rows[0].record_uuid)
        self.assertEqual(
            self.local_conn.execute("SELECT COUNT(*) FROM record_sync_state").fetchone()[0],
            1,
        )

    def test_sync_pushes_newer_local_changes_after_baseline_sync(self) -> None:
        record_id = insert_equipment(
            self.local_conn,
            Equipment(
                asset_number="ME-300",
                manufacturer="Starrett",
                manufacturer_raw="Starrett",
                description="Original local note",
            ),
        )
        first_result = sync_local_with_shared(self.local_conn, override_root=self.root)
        self.assertEqual(first_result.initialized, "shared")

        local_eq = get_all_equipment(self.local_conn, archived="all")[0]
        self.assertEqual(local_eq.record_id, record_id)
        local_eq.description = "Updated on this computer"
        update_equipment(self.local_conn, local_eq)

        second_result = sync_local_with_shared(self.local_conn, override_root=self.root)

        shared_conn = self._open_shared_conn()
        try:
            shared_eq = get_all_equipment(shared_conn, archived="all")[0]
        finally:
            shared_conn.close()

        self.assertEqual(second_result.pushed, 1)
        self.assertEqual(second_result.pulled, 0)
        self.assertEqual(shared_eq.description, "Updated on this computer")

    def test_sync_pulls_newer_shared_changes_after_baseline_sync(self) -> None:
        insert_equipment(
            self.local_conn,
            Equipment(
                asset_number="ME-400",
                manufacturer="Brown & Sharpe",
                manufacturer_raw="Brown & Sharpe",
                description="Original shared note",
            ),
        )
        first_result = sync_local_with_shared(self.local_conn, override_root=self.root)
        self.assertEqual(first_result.initialized, "shared")

        shared_conn = self._open_shared_conn()
        try:
            shared_eq = get_all_equipment(shared_conn, archived="all")[0]
            shared_eq.description = "Updated from another computer"
            update_equipment(shared_conn, shared_eq)
        finally:
            shared_conn.close()

        second_result = sync_local_with_shared(self.local_conn, override_root=self.root)
        local_eq = get_all_equipment(self.local_conn, archived="all")[0]

        self.assertEqual(second_result.pulled, 1)
        self.assertEqual(second_result.pushed, 0)
        self.assertEqual(local_eq.description, "Updated from another computer")

    def test_sync_reconciles_same_record_with_different_uuids_without_duplication(self) -> None:
        shared_conn = self._open_shared_conn()
        try:
            shared_id = insert_equipment(
                shared_conn,
                Equipment(
                    asset_number="ME-500",
                    manufacturer="Fluke",
                    manufacturer_raw="Fluke",
                    description="Shared source of truth",
                ),
            )
            shared_conn.execute(
                "UPDATE equipment SET updated_at='2026-04-17 09:00:00' WHERE record_id=?",
                (shared_id,),
            )
            shared_conn.commit()
            shared_eq = get_all_equipment(shared_conn, archived="all")[0]
        finally:
            shared_conn.close()

        local_id = insert_equipment(
            self.local_conn,
            Equipment(
                asset_number="ME-500",
                manufacturer="Fluke",
                manufacturer_raw="Fluke",
                description="Local updated note",
            ),
        )
        self.local_conn.execute(
            "UPDATE equipment SET updated_at='2026-04-17 10:00:00' WHERE record_id=?",
            (local_id,),
        )
        self.local_conn.commit()

        result = sync_local_with_shared(self.local_conn, override_root=self.root)

        local_rows = get_all_equipment(self.local_conn, archived="all")
        shared_conn = self._open_shared_conn()
        try:
            shared_rows = get_all_equipment(shared_conn, archived="all")
        finally:
            shared_conn.close()

        self.assertEqual(result.pushed, 1)
        self.assertEqual(result.pulled, 0)
        self.assertEqual(len(local_rows), 1)
        self.assertEqual(len(shared_rows), 1)
        self.assertEqual(local_rows[0].record_uuid, shared_eq.record_uuid)
        self.assertEqual(shared_rows[0].record_uuid, shared_eq.record_uuid)
        self.assertEqual(shared_rows[0].description, "Local updated note")

    def test_sync_removes_exact_duplicate_rows_before_merge(self) -> None:
        shared_conn = self._open_shared_conn()
        try:
            eq = Equipment(
                asset_number="ME-600",
                manufacturer="Mitutoyo",
                manufacturer_raw="Mitutoyo",
                description="Exact duplicate",
            )
            insert_equipment(shared_conn, eq)
            insert_equipment(
                shared_conn,
                Equipment(
                    asset_number=eq.asset_number,
                    manufacturer=eq.manufacturer,
                    manufacturer_raw=eq.manufacturer_raw,
                    description=eq.description,
                ),
            )
        finally:
            shared_conn.close()

        result = sync_local_with_shared(self.local_conn, override_root=self.root)

        shared_conn = self._open_shared_conn()
        try:
            shared_rows = get_all_equipment(shared_conn, archived="all")
        finally:
            shared_conn.close()

        self.assertEqual(len(shared_rows), 1)
        self.assertEqual(result.pulled, 1)
        self.assertEqual(result.conflicts, 0)

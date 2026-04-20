"""Regression tests for shared-first sync and update behavior."""

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from app_config import APP_CONFIG
from Code.db.database import (
    create_tables,
    get_all_equipment,
    get_connection,
    get_equipment_by_uuid,
    insert_equipment,
    load_sync_state,
    set_sync_state,
    update_equipment,
)
from Code.db.models import Equipment
from Code.sync.service import (
    check_for_update,
    sync_interval_ms,
    sync_local_with_shared,
)


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

    def _seed_shared_revision(self, conn) -> None:
        state = load_sync_state(conn)
        row = conn.execute(
            "SELECT MAX(TRIM(COALESCE(updated_at, ''))) AS latest_mutation FROM equipment"
        ).fetchone()
        latest_mutation = str(row["latest_mutation"] if hasattr(row, "keys") else row[0] or "").strip()
        set_sync_state(
            conn,
            revision=f"{latest_mutation or 'seed'}:seed",
            global_mutation_at=latest_mutation or state.get("global_mutation_at", ""),
            commit=True,
        )

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
        with patch("Code.sync.service.APP_CONFIG", SimpleNamespace(auto_sync_interval_ms=10000)):
            self.assertEqual(sync_interval_ms(), 10000)

        with patch("Code.sync.service.APP_CONFIG", SimpleNamespace(auto_sync_interval_ms=1000)):
            self.assertEqual(sync_interval_ms(), 5000)

    def test_sync_pulls_shared_snapshot_to_empty_local(self) -> None:
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
            self._seed_shared_revision(shared_conn)
        finally:
            shared_conn.close()

        result = sync_local_with_shared(self.local_conn, override_root=self.root)
        rows = get_all_equipment(self.local_conn, archived="all")

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].asset_number, "ME-100")
        self.assertTrue(result.shared_available)
        self.assertGreaterEqual(result.pulled, 1)

    def test_empty_authoritative_shared_snapshot_clears_divergent_local_cache(self) -> None:
        insert_equipment(
            self.local_conn,
            Equipment(
                asset_number="ME-200",
                manufacturer="Mitutoyo",
                manufacturer_raw="Mitutoyo",
                description="Stale local cache row",
            ),
        )

        shared_conn = self._open_shared_conn()
        try:
            set_sync_state(
                shared_conn,
                revision="2030-01-01T00:00:00.000000Z:authoritative-empty",
                global_mutation_at="2030-01-01T00:00:00.000000Z",
            )
        finally:
            shared_conn.close()

        result = sync_local_with_shared(self.local_conn, override_root=self.root)

        shared_conn = self._open_shared_conn()
        try:
            shared_rows = get_all_equipment(shared_conn, archived="all")
        finally:
            shared_conn.close()
        local_rows = get_all_equipment(self.local_conn, archived="all")

        self.assertEqual(len(shared_rows), 0)
        self.assertEqual(len(local_rows), 0)
        self.assertTrue(result.shared_available)
        self.assertGreaterEqual(result.pulled, 0)

    def test_sync_pulls_newer_shared_revision_after_baseline(self) -> None:
        shared_conn = self._open_shared_conn()
        try:
            insert_equipment(
                shared_conn,
                Equipment(
                    asset_number="ME-400",
                    manufacturer="Brown & Sharpe",
                    manufacturer_raw="Brown & Sharpe",
                    description="Original authoritative note",
                ),
            )
            self._seed_shared_revision(shared_conn)
        finally:
            shared_conn.close()

        sync_local_with_shared(self.local_conn, override_root=self.root)

        shared_conn = self._open_shared_conn()
        try:
            shared_eq = get_all_equipment(shared_conn, archived="all")[0]
            shared_eq.description = "Updated from another computer"
            shared_eq.updated_at = "2030-01-01T00:00:00.000000Z"
            update_equipment(shared_conn, shared_eq)
            set_sync_state(
                shared_conn,
                revision="2030-01-01T00:00:00.000000Z:remote",
                global_mutation_at=shared_eq.updated_at,
            )
        finally:
            shared_conn.close()

        second_result = sync_local_with_shared(self.local_conn, override_root=self.root)
        local_eq = get_all_equipment(self.local_conn, archived="all")[0]

        self.assertEqual(local_eq.description, "Updated from another computer")
        self.assertTrue(second_result.shared_available)
        self.assertGreaterEqual(second_result.pulled, 1)

    def test_shared_authoritative_snapshot_overwrites_divergent_local_cache(self) -> None:
        shared_conn = self._open_shared_conn()
        try:
            insert_equipment(
                shared_conn,
                Equipment(
                    asset_number="ME-500",
                    manufacturer="Mitutoyo",
                    manufacturer_raw="Mitutoyo",
                    description="Baseline",
                ),
            )
            self._seed_shared_revision(shared_conn)
        finally:
            shared_conn.close()

        sync_local_with_shared(self.local_conn, override_root=self.root)
        local_eq = get_all_equipment(self.local_conn, archived="all")[0]
        local_eq.description = "Locally diverged cache value"
        update_equipment(self.local_conn, local_eq)

        shared_conn = self._open_shared_conn()
        try:
            shared_eq = get_equipment_by_uuid(shared_conn, local_eq.record_uuid)
            assert shared_eq is not None
            shared_eq.description = "Authoritative shared value"
            shared_eq.updated_at = "2099-01-01T00:00:00.000000Z"
            update_equipment(shared_conn, shared_eq)
            set_sync_state(
                shared_conn,
                revision="2099-01-01T00:00:00.000000Z:remote",
                global_mutation_at=shared_eq.updated_at,
            )
        finally:
            shared_conn.close()

        result = sync_local_with_shared(self.local_conn, override_root=self.root)
        refreshed = get_all_equipment(self.local_conn, archived="all")[0]

        self.assertEqual(refreshed.description, "Authoritative shared value")
        self.assertTrue(result.shared_available)
        self.assertGreaterEqual(result.pulled, 1)


if __name__ == "__main__":
    unittest.main()

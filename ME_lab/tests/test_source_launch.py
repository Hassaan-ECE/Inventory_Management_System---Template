"""Tests for source-run launch helpers."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from source_launch import configure_source_db_path


class SourceLaunchTests(unittest.TestCase):
    def test_source_run_stays_repo_local_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            local_appdata = Path(temp_dir) / "AppData"
            db_path = local_appdata / "ME_Lab_Inventory" / "me_lab_inventory.db"
            db_path.parent.mkdir(parents=True, exist_ok=True)
            db_path.write_text("", encoding="utf-8")

            with patch.dict(os.environ, {"LOCALAPPDATA": str(local_appdata)}, clear=False):
                os.environ.pop("ME_LAB_INVENTORY_DB_PATH", None)
                os.environ.pop("ME_LAB_SOURCE_USE_INSTALLED_DB", None)
                selected = configure_source_db_path()
                configured = os.environ.get("ME_LAB_INVENTORY_DB_PATH")

            self.assertIsNone(selected)
            self.assertIsNone(configured)

    def test_uses_installed_local_db_when_explicitly_requested(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            local_appdata = Path(temp_dir) / "AppData"
            db_path = local_appdata / "ME_Lab_Inventory" / "me_lab_inventory.db"
            db_path.parent.mkdir(parents=True, exist_ok=True)
            db_path.write_text("", encoding="utf-8")

            with patch.dict(
                os.environ,
                {
                    "LOCALAPPDATA": str(local_appdata),
                    "ME_LAB_SOURCE_USE_INSTALLED_DB": "1",
                },
                clear=False,
            ):
                os.environ.pop("ME_LAB_INVENTORY_DB_PATH", None)
                selected = configure_source_db_path()
                configured = os.environ.get("ME_LAB_INVENTORY_DB_PATH")

            self.assertEqual(selected, db_path)
            self.assertEqual(configured, str(db_path))

    def test_preserves_explicit_db_override(self) -> None:
        override = Path(r"C:\temp\custom_me_lab.db")
        with patch.dict(
            os.environ,
            {
                "LOCALAPPDATA": r"C:\ignored",
                "ME_LAB_INVENTORY_DB_PATH": str(override),
            },
            clear=False,
        ):
            selected = configure_source_db_path()
            configured = os.environ.get("ME_LAB_INVENTORY_DB_PATH")

        self.assertEqual(selected, override)
        self.assertEqual(configured, str(override))

    def test_returns_none_when_installed_db_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            local_appdata = Path(temp_dir) / "AppData"

            with patch.dict(os.environ, {"LOCALAPPDATA": str(local_appdata)}, clear=False):
                os.environ.pop("ME_LAB_INVENTORY_DB_PATH", None)
                selected = configure_source_db_path()

            self.assertIsNone(selected)
            self.assertNotIn("ME_LAB_INVENTORY_DB_PATH", os.environ)

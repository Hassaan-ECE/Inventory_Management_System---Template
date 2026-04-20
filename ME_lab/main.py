"""ME Lab Inventory Manager entry point."""

import sys
from pathlib import Path

SHARED_ROOT = Path(__file__).resolve().parent.parent / "shared_core"
if str(SHARED_ROOT) not in sys.path:
    sys.path.insert(0, str(SHARED_ROOT))

from app_config import APP_CONFIG
from Code.app_bootstrap import run_app, expected_source_files, StartupSplash
from Code.db.database import get_database_path
from Code.utils.runtime_paths import resolve_data_dir
from source_launch import configure_source_db_path

from Code.gui.main_window import MainWindow
from Code.gui.theme import DEFAULT_THEME_NAME
from Code.sync.service import run_excel_import, shared_sync_enabled, sync_local_from_shared
from PySide6.QtWidgets import QMessageBox


def main():
    configure_source_db_path()
    sys.exit(
        run_app(
            lambda conn: MainWindow(conn, initial_theme_name=DEFAULT_THEME_NAME),
            APP_CONFIG.application_name,
            theme_name=DEFAULT_THEME_NAME,
            startup_task=_run_startup_sync,
            first_run_import=_run_initial_import,
        )
    )


def _run_startup_sync(app, conn, splash) -> None:
    """Optional startup sync for shared-workspace environments."""
    if not shared_sync_enabled():
        return

    splash.set_status("Checking shared workspace...")
    try:
        sync_result = sync_local_from_shared(conn, force=True)
        if sync_result.message:
            splash.set_status(sync_result.message)
            app.processEvents()
    except Exception:
        splash.set_status("Shared workspace unavailable. Continuing with local data.")


def _run_initial_import(app, _conn, splash: StartupSplash):
    """Run the import pipeline on first launch."""
    data_dir = resolve_data_dir()
    required_files = expected_source_files()
    missing = [
        (name, (data_dir / name).exists())
        for name in required_files
    ]

    if not all(found for _, found in missing):
        splash.set_status("Data files are missing.")
        QMessageBox.warning(
            None,
            "Data Files Missing",
            f"Expected data files not found in:\n{data_dir}\n\n"
            + "\n".join(f"{name}: {'Found' if found else 'MISSING'}" for name, found in missing)
            + "\n\n"
            "The app will start with an empty database.\n"
            "Use 'Import Data' once the files are in place.",
        )
        return

    splash.set_status("Importing inventory data for first launch...")

    def on_progress(step, detail):
        splash.set_status(f"{step}: {detail}")
        app.processEvents()

    try:
        if shared_sync_enabled():
            local_db_path = get_database_path(_conn)
            if local_db_path is None:
                raise RuntimeError("Local database path is not available for startup import.")
            stats = run_excel_import(local_db_path, data_dir, mode="full", progress_callback=on_progress)
        else:
            from Code.importer.pipeline import run_full_import

            stats = run_full_import(data_dir, progress_callback=on_progress)
        splash.set_status("Import complete.")

        QMessageBox.information(
            None,
            "Import Complete",
            f"Successfully imported inventory data.\n\n"
            f"Equipment records: {stats.get('base_records', 0)}\n"
            f"Survey matches: {stats.get('survey_matched', 0)}\n"
            f"Raw cells indexed: {stats.get('total_raw_cells', 0)}\n"
            f"Import issues to review: {stats.get('total_issues', 0)}",
        )

    except Exception as exc:
        splash.set_status("Import failed.")
        QMessageBox.critical(
            None,
            "Import Error",
            f"Failed to import data:\n\n{exc}\n\n"
            "The app will start with an empty database.\n"
            "Check the Data/ folder and try 'Import Data'.",
        )


if __name__ == "__main__":
    main()

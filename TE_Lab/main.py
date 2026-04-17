"""TE Lab Equipment Inventory Manager — Entry point."""

import sys
from pathlib import Path

SHARED_ROOT = Path(__file__).resolve().parent.parent / "shared_core"
if str(SHARED_ROOT) not in sys.path:
    sys.path.insert(0, str(SHARED_ROOT))

from app_config import APP_CONFIG
from Code.app_bootstrap import expected_source_files, run_app, StartupSplash
from Code.utils.runtime_paths import resolve_data_dir
from PySide6.QtWidgets import QMessageBox

from Code.gui.main_window import MainWindow
from Code.gui.theme import DEFAULT_THEME_NAME


def main():
    sys.exit(
        run_app(
            lambda conn: MainWindow(conn, initial_theme_name=DEFAULT_THEME_NAME),
            APP_CONFIG.application_name,
            theme_name=DEFAULT_THEME_NAME,
            first_run_import=_run_initial_import,
        )
    )


def _run_initial_import(app, _conn, splash: StartupSplash):
    """Run the import pipeline on first launch."""
    data_dir = resolve_data_dir()

    required_files = expected_source_files()
    missing = [(name, (data_dir / name).exists()) for name in required_files]
    if not all(found for _, found in missing):
        splash.set_status("Data files are missing.")
        QMessageBox.warning(
            None,
            "Data Files Missing",
            f"Expected data files not found in:\n{data_dir}\n\n"
            + "\n".join(f"{name}: {'Found' if found else 'MISSING'}" for name, found in missing)
            + "\n\n"
            "The app will start with an empty database.\n"
            "Use 'Import Data' once the files are in place."
        )
        return

    splash.set_status("Importing equipment data for first launch...")

    def on_progress(step, detail):
        splash.set_status(f"{step}: {detail}")
        app.processEvents()

    try:
        from Code.importer.pipeline import run_full_import

        stats = run_full_import(data_dir, progress_callback=on_progress)
        splash.set_status("Import complete.")

        QMessageBox.information(
            None, "Import Complete",
            f"Successfully imported equipment data.\n\n"
            f"Equipment records: {stats['base_records']}\n"
            f"Survey matches: {stats['survey_matched']}\n"
            f"Raw cells indexed: {stats['total_raw_cells']}\n"
            f"Import issues to review: {stats['total_issues']}"
        )

    except Exception as e:
        splash.set_status("Import failed.")
        QMessageBox.critical(
            None, "Import Error",
            f"Failed to import data:\n\n{e}\n\n"
            "The app will start with an empty database.\n"
            "Check the Data/ folder and try 'Import Data'."
        )


if __name__ == "__main__":
    main()

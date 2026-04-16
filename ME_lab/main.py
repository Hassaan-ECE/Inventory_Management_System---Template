"""ME Lab Inventory Manager entry point.

Run this file to launch the application:
    python main.py
"""

import sys
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parent
SHARED_ROOT = APP_ROOT.parent / "shared_core"
if str(SHARED_ROOT) not in sys.path:
    sys.path.insert(0, str(SHARED_ROOT))

from app_config import APP_CONFIG
from Code.utils.runtime_paths import resolve_data_dir

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication, QLabel, QMessageBox, QVBoxLayout, QWidget

from Code.db.database import create_tables, get_connection
from Code.gui.main_window import MainWindow
from Code.gui.theme import DEFAULT_THEME_NAME, get_stylesheet
from Code.gui.window_branding import APPLICATION_WINDOW_TITLE, app_icon, apply_window_branding
from Code.importer.master_parser import MASTER_FILE
from Code.importer.survey_parser import SURVEY_FILE
from Code.sync.service import shared_sync_enabled, sync_local_with_shared


def main():
    app = QApplication(sys.argv)
    app.setApplicationName(APP_CONFIG.application_name)
    icon = app_icon()
    if not icon.isNull():
        app.setWindowIcon(icon)
    app.setStyleSheet(get_stylesheet(DEFAULT_THEME_NAME))

    splash = StartupSplash()
    splash.show()
    splash.raise_()
    app.processEvents()
    splash.set_status("Loading application...")

    splash.set_status("Opening database...")
    conn = get_connection()
    splash.set_status("Preparing database...")
    create_tables(conn)
    if shared_sync_enabled():
        splash.set_status("Checking shared workspace...")
        try:
            sync_result = sync_local_with_shared(conn)
            if sync_result.message:
                splash.set_status(sync_result.message)
                app.processEvents()
        except Exception:
            splash.set_status("Shared workspace unavailable. Continuing with local data.")

    splash.set_status("Checking inventory records...")
    count = conn.execute("SELECT COUNT(*) FROM equipment").fetchone()[0]
    if count == 0:
        _run_initial_import(app, conn, splash)

    splash.set_status("Opening inventory window...")
    window = MainWindow(conn, initial_theme_name=DEFAULT_THEME_NAME)
    window.show()
    splash.close()

    exit_code = app.exec()
    conn.close()
    sys.exit(exit_code)


class StartupSplash(QWidget):
    """Small startup window shown before the main UI is ready."""

    def __init__(self):
        super().__init__()
        apply_window_branding(self, "Starting Up")
        self.setObjectName("panelCard")
        self.setWindowFlags(Qt.Window | Qt.CustomizeWindowHint | Qt.WindowTitleHint)
        self.setFixedSize(520, 190)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(10)

        title = QLabel(APPLICATION_WINDOW_TITLE)
        title.setObjectName("pageTitle")
        title.setStyleSheet("font-size: 28px; font-weight: 700;")
        layout.addWidget(title)

        subtitle = QLabel("Starting up")
        subtitle.setObjectName("sectionSubheader")
        layout.addWidget(subtitle)

        self.status_label = QLabel("Loading...")
        self.status_label.setObjectName("sectionHeader")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)
        layout.addStretch()

        self._center_on_screen()

    def _center_on_screen(self) -> None:
        screen = QGuiApplication.primaryScreen()
        if screen is None:
            return

        available = screen.availableGeometry()
        frame = self.frameGeometry()
        frame.moveCenter(available.center())
        self.move(frame.topLeft())

    def set_status(self, text: str) -> None:
        self.status_label.setText(text)
        QApplication.processEvents()


def _run_initial_import(app: QApplication, conn, splash: StartupSplash):
    """Run the import pipeline on first launch."""
    data_dir = resolve_data_dir()
    required_files = _expected_source_files()
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
        from Code.importer.pipeline import run_full_import

        stats = run_full_import(data_dir, progress_callback=on_progress)
        splash.set_status("Import complete.")

        QMessageBox.information(
            None,
            "Import Complete",
            f"Successfully imported inventory data.\n\n"
            f"Equipment records: {stats['base_records']}\n"
            f"Survey matches: {stats['survey_matched']}\n"
            f"Raw cells indexed: {stats['total_raw_cells']}\n"
            f"Import issues to review: {stats['total_issues']}",
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


def _expected_source_files() -> list[str]:
    """Return the configured Excel sources required for the current app."""
    files = [MASTER_FILE]
    if SURVEY_FILE:
        files.append(SURVEY_FILE)
    return files


if __name__ == "__main__":
    main()

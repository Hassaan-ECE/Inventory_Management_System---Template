"""TE Lab Equipment Inventory Manager — Entry point.

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
from Code.importer.master_parser import MASTER_FILE
from Code.importer.survey_parser import SURVEY_FILE


def main():
    app = QApplication(sys.argv)
    app.setApplicationName(APP_CONFIG.application_name)
    app.setStyleSheet(get_stylesheet(DEFAULT_THEME_NAME))

    splash = StartupSplash()
    splash.show()
    splash.set_status("Loading application...")

    # Initialize database
    splash.set_status("Opening database...")
    conn = get_connection()
    splash.set_status("Preparing database...")
    create_tables(conn)

    # Check if this is first run (no equipment data yet)
    splash.set_status("Checking inventory records...")
    count = conn.execute("SELECT COUNT(*) FROM equipment").fetchone()[0]
    if count == 0:
        _run_initial_import(app, conn, splash)

    # Launch main window
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
        self.setWindowTitle(APP_CONFIG.display_name)
        self.setObjectName("panelCard")
        self.setWindowFlags(Qt.Window | Qt.CustomizeWindowHint | Qt.WindowTitleHint)
        self.setFixedSize(420, 180)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(10)

        title = QLabel(APP_CONFIG.display_name)
        title.setObjectName("pageTitle")
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

    master = data_dir / MASTER_FILE
    survey = data_dir / SURVEY_FILE

    if not master.exists() or not survey.exists():
        splash.set_status("Data files are missing.")
        QMessageBox.warning(
            None, "Data Files Missing",
            f"Expected data files not found in:\n{data_dir}\n\n"
            f"{MASTER_FILE}: {'Found' if master.exists() else 'MISSING'}\n"
            f"{SURVEY_FILE}: {'Found' if survey.exists() else 'MISSING'}\n\n"
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

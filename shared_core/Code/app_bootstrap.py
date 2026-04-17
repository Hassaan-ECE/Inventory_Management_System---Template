"""Shared startup bootstrap for inventory app variants."""

from __future__ import annotations

import sqlite3
import sys
from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication, QLabel, QMessageBox, QVBoxLayout, QWidget

from Code.db.database import create_tables, get_connection
from Code.gui.theme import DEFAULT_THEME_NAME, get_stylesheet
from Code.gui.window_branding import APPLICATION_WINDOW_TITLE, app_icon, apply_window_branding
from Code.importer.master_parser import MASTER_FILE
from Code.importer.survey_parser import SURVEY_FILE

StartupTask = Callable[[QApplication, sqlite3.Connection, "StartupSplash"], None]
MainWindowFactory = Callable[[sqlite3.Connection], QWidget]


def expected_source_files() -> list[str]:
    """Return the expected source workbook file names for the active app config."""
    files = [MASTER_FILE]
    if SURVEY_FILE:
        files.append(SURVEY_FILE)
    return files


def run_app(
    make_main_window: MainWindowFactory,
    app_name: str,
    *,
    theme_name: str = DEFAULT_THEME_NAME,
    startup_task: StartupTask | None = None,
    first_run_import: StartupTask | None = None,
) -> int:
    """Start the app with standardized bootstrap and optional startup hooks."""
    app = QApplication(sys.argv)
    app.setApplicationName(app_name)
    icon = app_icon()
    if not icon.isNull():
        app.setWindowIcon(icon)
    app.setStyleSheet(get_stylesheet(theme_name))

    conn: sqlite3.Connection | None = None
    splash: StartupSplash | None = None
    exit_code = 0

    try:
        splash = StartupSplash()
        splash.show()
        splash.raise_()
        app.processEvents()
        splash.set_status("Loading application...")

        splash.set_status("Opening database...")
        conn = get_connection()
        splash.set_status("Preparing database...")
        create_tables(conn)

        if startup_task is not None:
            try:
                startup_task(app, conn, splash)
            except Exception as exc:
                splash.set_status("Startup task failed.")
                QMessageBox.warning(
                    None,
                    "Startup Task Failed",
                    f"An optional startup task failed:\n\n{exc}\n\n"
                    "The app will continue with local data.",
                )

        splash.set_status("Checking inventory records...")
        count = conn.execute("SELECT COUNT(*) FROM equipment").fetchone()[0]
        if count == 0 and first_run_import is not None:
            try:
                first_run_import(app, conn, splash)
            except Exception as exc:
                splash.set_status("Initial import failed.")
                QMessageBox.critical(
                    None,
                    "Initial Import Error",
                    f"Failed to import source data:\n\n{exc}\n\n"
                    "The app will start with an empty database.",
                )

        splash.set_status("Opening inventory window...")
        window = make_main_window(conn)
        window.show()
        splash.close()

        exit_code = app.exec()
    finally:
        if splash is not None:
            splash.close()
        if conn is not None:
            conn.close()

    return exit_code


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

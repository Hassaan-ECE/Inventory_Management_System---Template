"""Sync lifecycle helpers extracted from the main window integration class."""

from __future__ import annotations

from PySide6.QtCore import QThread

from Code.db.database import get_database_path
from Code.sync.worker import GuiSyncWorker


def setup_sync_worker(window) -> None:
    """Create a dedicated worker thread that owns sync runtime calls."""
    if window._sync_worker is not None:
        return

    db_path = get_database_path(window.conn)
    if db_path is None:
        window.status_bar.showMessage("Shared sync unavailable: local database path not found.", 5000)
        return

    window._sync_thread = QThread(window)

    window._sync_worker = GuiSyncWorker(db_path)
    window._sync_worker.moveToThread(window._sync_thread)

    window.request_startup_sync.connect(window._sync_worker.run_startup_sync)
    window.request_sync.connect(window._sync_worker.run_sync)
    window.request_revision_check.connect(window._sync_worker.run_revision_check)
    window.request_reconnect.connect(window._sync_worker.run_reconnect)
    window.request_shutdown_sync.connect(window._sync_worker.shutdown)

    window._sync_worker.sync_completed.connect(window._on_sync_completed)
    window._sync_worker.sync_failed.connect(window._on_sync_failed)
    window._sync_worker.revision_checked.connect(window._on_revision_checked)
    window._sync_worker.status_message.connect(window._on_worker_status_message)

    window._sync_thread.start()


def teardown_sync_worker(window) -> None:
    """Stop and clean up the sync worker thread."""
    if window._sync_worker is None or window._sync_thread is None:
        return

    window.request_shutdown_sync.emit()
    window._sync_thread.quit()
    window._sync_thread.wait(2500)
    window._sync_worker.deleteLater()
    window._sync_thread.deleteLater()
    window._sync_worker = None
    window._sync_thread = None


def run_shared_sync(window, quiet: bool = False) -> None:
    """Request a background revision check and pull when needed."""
    del quiet
    from Code.gui import main_window as main_window_module

    if not main_window_module.shared_sync_enabled():
        return
    window.request_revision_check.emit("periodic")


__all__ = [
    "run_shared_sync",
    "setup_sync_worker",
    "teardown_sync_worker",
]

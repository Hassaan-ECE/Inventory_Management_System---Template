"""Qt worker bridge for background shared-first sync operations."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, Signal, Slot

from Code.sync import service as sync_service


class GuiSyncWorker(QObject):
    """Run shared revision checks and local cache refresh work off the GUI thread."""

    sync_completed = Signal(object)
    sync_failed = Signal(str, bool)
    revision_checked = Signal(bool, str)
    status_message = Signal(str, int)

    def __init__(self, db_path: Path):
        super().__init__()
        self._db_path = Path(db_path)

    @Slot()
    def run_startup_sync(self) -> None:
        self._run_sync(quiet=True, force=True)

    @Slot(bool, str)
    def run_sync(self, quiet: bool, reason: str) -> None:
        del reason
        self._run_sync(quiet=quiet, force=False)

    @Slot(str)
    def run_revision_check(self, _reason: str) -> None:
        try:
            result = sync_service.check_revision(self._db_path)
            payload = self._serialize(result)
            if payload.get("busy"):
                self.status_message.emit(payload.get("message") or "Shared workspace busy, retry in a moment.", 3500)
            elif not payload.get("shared_available"):
                self.status_message.emit(payload.get("message") or "Shared workspace unavailable. Viewing local cache only.", 5000)
            token = str(payload.get("shared_revision") or payload.get("local_revision") or "")
            self.revision_checked.emit(bool(payload.get("needs_sync")), token)
        except Exception as exc:
            self.status_message.emit(f"Shared sync check failed: {exc}", 5000)
            self.revision_checked.emit(False, "")

    @Slot()
    def run_reconnect(self) -> None:
        self._run_sync(quiet=True, force=True)

    @Slot()
    def shutdown(self) -> None:
        return

    def _run_sync(self, *, quiet: bool, force: bool) -> None:
        try:
            result = sync_service.sync_local_from_shared(self._db_path, force=force)
            payload = self._serialize(result)
            self.sync_completed.emit(payload)
            message = str(payload.get("message", "") or "").strip()
            if message:
                self.status_message.emit(message, 5000)
        except Exception as exc:
            self.sync_failed.emit(str(exc), quiet)

    @staticmethod
    def _serialize(result: Any) -> Any:
        if result is None:
            return None
        if isinstance(result, (str, int, float, bool)):
            return result
        if isinstance(result, dict):
            return dict(result)
        if is_dataclass(result):
            return asdict(result)
        if isinstance(result, Path):
            return str(result)
        return result

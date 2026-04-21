"""CRUD/archive/import action helpers extracted from the main window shell."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QMessageBox

from Code.db.database import (
    delete_equipment as delete_equipment_local,
    import_database_snapshot as import_database_snapshot_local,
    insert_equipment as insert_equipment_local,
    update_equipment as update_equipment_local,
)


def submit_create_equipment(window, equipment, action: str = "create") -> None:
    """Persist a new record through the active runtime path."""
    from Code.gui import main_window as main_window_module

    if main_window_module.shared_sync_enabled():
        if not window._can_modify_records():
            return
        try:
            main_window_module.create_equipment_shared(window.conn, equipment)
        except TimeoutError as exc:
            window.status_bar.showMessage(str(exc) or "Shared workspace busy, retry in a moment.", 4000)
            return
        except ConnectionError as exc:
            window._set_shared_actions_enabled(False)
            window.status_bar.showMessage(str(exc) or "Shared workspace unavailable. Viewing local cache only.", 5000)
            return
        window._do_search()
        window._update_status_bar()
        window.status_bar.showMessage(window._mutation_success_message(action), 3000)
        return
    insert_equipment_local(window.conn, equipment)
    window._do_search()
    window._update_status_bar()
    window.status_bar.showMessage(window._mutation_success_message(action), 3000)


def submit_update_equipment(window, equipment, action: str = "update") -> None:
    """Persist an updated record through the active runtime path."""
    from Code.gui import main_window as main_window_module

    if main_window_module.shared_sync_enabled():
        if not window._can_modify_records():
            return
        try:
            main_window_module.update_equipment_shared(window.conn, equipment)
        except TimeoutError as exc:
            window.status_bar.showMessage(str(exc) or "Shared workspace busy, retry in a moment.", 4000)
            return
        except ConnectionError as exc:
            window._set_shared_actions_enabled(False)
            window.status_bar.showMessage(str(exc) or "Shared workspace unavailable. Viewing local cache only.", 5000)
            return
        window._do_search()
        window._update_status_bar()
        window.status_bar.showMessage(window._mutation_success_message(action), 3000)
        return
    update_equipment_local(window.conn, equipment)
    window._do_search()
    window._update_status_bar()
    window.status_bar.showMessage(window._mutation_success_message(action), 3000)


def submit_archive_change(window, record_uuid: str, archived: bool) -> None:
    """Persist archive-state changes through the appropriate runtime path."""
    from Code.gui import main_window as main_window_module

    action = "archive" if archived else "restore"
    if main_window_module.shared_sync_enabled():
        if not window._can_modify_records():
            return
        try:
            main_window_module.set_archived_shared(window.conn, record_uuid, archived)
        except TimeoutError as exc:
            window.status_bar.showMessage(str(exc) or "Shared workspace busy, retry in a moment.", 4000)
            return
        except ConnectionError as exc:
            window._set_shared_actions_enabled(False)
            window.status_bar.showMessage(str(exc) or "Shared workspace unavailable. Viewing local cache only.", 5000)
            return
        window._do_search()
        window._update_status_bar()
        window.status_bar.showMessage(window._mutation_success_message(action), 3000)
        return
    eq = window._equipment_for_record_uuid(record_uuid)
    if eq is None:
        raise KeyError(f"Equipment record not found: {record_uuid}")
    eq.is_archived = archived
    update_equipment_local(window.conn, eq)
    window._do_search()
    window._update_status_bar()
    window.status_bar.showMessage(window._mutation_success_message(action), 3000)


def submit_delete_record(window, record_id: int, record_uuid: str) -> None:
    """Delete a record through the active runtime path."""
    from Code.gui import main_window as main_window_module

    if main_window_module.shared_sync_enabled():
        if not window._can_modify_records():
            return
        try:
            main_window_module.delete_equipment_shared(window.conn, record_uuid)
        except TimeoutError as exc:
            window.status_bar.showMessage(str(exc) or "Shared workspace busy, retry in a moment.", 4000)
            return
        except ConnectionError as exc:
            window._set_shared_actions_enabled(False)
            window.status_bar.showMessage(str(exc) or "Shared workspace unavailable. Viewing local cache only.", 5000)
            return
        window._do_search()
        window._update_status_bar()
        window.status_bar.showMessage(window._mutation_success_message("delete"), 3000)
        return
    delete_equipment_local(window.conn, record_id)
    window._do_search()
    window._update_status_bar()
    window.status_bar.showMessage(window._mutation_success_message("delete"), 3000)


def submit_toggle_verified(window, record_uuid: str) -> None:
    """Toggle verification through the active runtime path."""
    from Code.gui import main_window as main_window_module

    if main_window_module.shared_sync_enabled():
        if not window._can_modify_records():
            return
        try:
            main_window_module.toggle_verified_shared(window.conn, record_uuid)
        except TimeoutError as exc:
            window.status_bar.showMessage(str(exc) or "Shared workspace busy, retry in a moment.", 4000)
            return
        except ConnectionError as exc:
            window._set_shared_actions_enabled(False)
            window.status_bar.showMessage(str(exc) or "Shared workspace unavailable. Viewing local cache only.", 5000)
            return
        window._do_search()
        window._update_status_bar()
        window.status_bar.showMessage(window._mutation_success_message("verify"), 3000)
        return
    eq = window._equipment_for_record_uuid(record_uuid)
    if eq is None:
        raise KeyError(f"Equipment record not found: {record_uuid}")
    eq.verified_in_survey = not eq.verified_in_survey
    update_equipment_local(window.conn, eq)
    window._do_search()
    window._update_status_bar()
    window.status_bar.showMessage(window._mutation_success_message("verify"), 3000)


def submit_excel_import(window, data_dir: Path, mode: str = "merge") -> None:
    """Run an Excel import through the active runtime path."""
    from Code.gui import main_window as main_window_module

    if main_window_module.shared_sync_enabled():
        if not window._can_modify_records():
            return
        try:
            stats = main_window_module.run_excel_import_shared(window.conn, data_dir, mode=mode)
        except TimeoutError as exc:
            window.status_bar.showMessage(str(exc) or "Shared workspace busy, retry in a moment.", 4000)
            return
        except ConnectionError as exc:
            window._set_shared_actions_enabled(False)
            window.status_bar.showMessage(str(exc) or "Shared workspace unavailable. Viewing local cache only.", 5000)
            return
        window._do_search()
        window._update_status_bar()
        QMessageBox.information(window, "Import Complete", window._format_import_success_message(f"excel_{mode}", stats))
        return

    from Code.importer.pipeline import run_full_import, run_merge_import

    runner = run_merge_import if mode == "merge" else run_full_import
    stats = runner(data_dir)
    window._do_search()
    window._update_status_bar()
    QMessageBox.information(window, "Import Complete", window._format_import_success_message(f"excel_{mode}", stats))


def submit_database_import(window, source_path: Path) -> None:
    """Run a database import through the active runtime path."""
    from Code.gui import main_window as main_window_module

    if main_window_module.shared_sync_enabled():
        if not window._can_modify_records():
            return
        try:
            stats = main_window_module.import_database_shared(window.conn, source_path)
        except TimeoutError as exc:
            window.status_bar.showMessage(str(exc) or "Shared workspace busy, retry in a moment.", 4000)
            return
        except ConnectionError as exc:
            window._set_shared_actions_enabled(False)
            window.status_bar.showMessage(str(exc) or "Shared workspace unavailable. Viewing local cache only.", 5000)
            return
        window._do_search()
        window._update_status_bar()
        QMessageBox.information(window, "Import Complete", window._format_import_success_message("db_snapshot", stats))
        return

    stats = import_database_snapshot_local(window.conn, source_path)
    window._do_search()
    window._update_status_bar()
    QMessageBox.information(window, "Import Complete", window._format_import_success_message("db_snapshot", stats))


__all__ = [
    "submit_archive_change",
    "submit_create_equipment",
    "submit_database_import",
    "submit_delete_record",
    "submit_excel_import",
    "submit_toggle_verified",
    "submit_update_equipment",
]

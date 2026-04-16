"""Local-first shared sync and update checks for internal inventory apps."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import socket
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from app_config import APP_CONFIG
from Code.db.database import (
    _build_equipment_search_text,
    create_tables,
    get_all_equipment,
    get_connection,
    get_database_path,
    import_database_snapshot,
)
from Code.db.models import Equipment
from Code.utils.runtime_paths import (
    shared_backup_dir,
    shared_database_dir,
    shared_db_path,
    shared_lock_path,
    shared_release_manifest_path,
    shared_root_dir,
)

_LOCK_STALE_SECONDS = 15 * 60
_SYNC_HASH_FIELDS = (
    "asset_number",
    "serial_number",
    "manufacturer",
    "manufacturer_raw",
    "model",
    "description",
    "qty",
    "location",
    "assigned_to",
    "ownership_type",
    "rental_vendor",
    "rental_cost_monthly",
    "calibration_status",
    "last_calibration_date",
    "calibration_due_date",
    "calibration_vendor",
    "calibration_cost",
    "lifecycle_status",
    "working_status",
    "condition",
    "acquired_date",
    "estimated_age_years",
    "age_basis",
    "verified_in_survey",
    "blue_dot_ref",
    "project_name",
    "picture_path",
    "links",
    "notes",
    "manual_entry",
    "is_archived",
    "source_refs",
)


@dataclass(frozen=True, slots=True)
class SyncResult:
    enabled: bool = False
    shared_available: bool = False
    initialized: str = ""
    pushed: int = 0
    pulled: int = 0
    conflicts: int = 0
    message: str = ""


@dataclass(frozen=True, slots=True)
class UpdateInfo:
    version: str
    installer_path: Path
    published_at: str = ""
    notes: str = ""


def shared_sync_enabled() -> bool:
    """Return whether this app variant is configured to use shared sync."""
    return bool(getattr(APP_CONFIG, "enable_shared_sync", False))


def update_checks_enabled() -> bool:
    """Return whether this app variant should look for newer releases."""
    return bool(getattr(APP_CONFIG, "enable_update_checks", False))


def sync_local_with_shared(local_conn, override_root: Path | None = None) -> SyncResult:
    """Merge the local database with the configured shared database when safe."""
    if not shared_sync_enabled():
        return SyncResult(message="Shared sync is disabled for this app.")

    root = _resolve_shared_root(override_root)
    if root is None:
        return SyncResult(enabled=True, message="Shared sync path is not configured.")
    if not root.exists():
        return SyncResult(enabled=True, message="Shared workspace is unavailable right now.")

    try:
        shared_dir = _resolve_shared_database_dir(override_root, create=True)
        backups_dir = _resolve_shared_backup_dir(override_root, create=True)
        shared_path = _resolve_shared_db_path(override_root)
        lock_path = _resolve_shared_lock_path(override_root)
    except OSError:
        return SyncResult(enabled=True, message="Shared workspace is unavailable right now.")

    if shared_dir is None or backups_dir is None or shared_path is None or lock_path is None:
        return SyncResult(enabled=True, message="Shared sync paths could not be resolved.")

    local_path = get_database_path(local_conn)
    if local_path is None:
        return SyncResult(enabled=True, shared_available=True, message="Local database path could not be resolved.")

    create_tables(local_conn)

    try:
        with _shared_lock(lock_path):
            shared_conn = get_connection(shared_path, use_wal=False)
            try:
                create_tables(shared_conn)

                local_count = _equipment_count(local_conn)
                shared_count = _equipment_count(shared_conn)

                if local_count == 0 and shared_count > 0:
                    import_database_snapshot(local_conn, shared_path)
                    create_tables(local_conn)
                    _rebuild_local_sync_state(local_conn)
                    return SyncResult(
                        enabled=True,
                        shared_available=True,
                        initialized="local",
                        pulled=shared_count,
                        message=f"Pulled {shared_count} shared records into this computer's database.",
                    )

                if shared_count == 0 and local_count > 0:
                    import_database_snapshot(shared_conn, local_path)
                    create_tables(shared_conn)
                    _rebuild_local_sync_state(local_conn)
                    return SyncResult(
                        enabled=True,
                        shared_available=True,
                        initialized="shared",
                        pushed=local_count,
                        message=f"Published {local_count} local records to the shared database.",
                    )

                state_by_uuid = _load_record_sync_state(local_conn)
                local_rows = {eq.record_uuid: eq for eq in get_all_equipment(local_conn, archived="all") if eq.record_uuid}
                shared_rows = {eq.record_uuid: eq for eq in get_all_equipment(shared_conn, archived="all") if eq.record_uuid}

                pushed = 0
                pulled = 0
                conflicts = 0
                backed_up_shared = False

                for record_uuid in sorted(set(local_rows) | set(shared_rows)):
                    local_eq = local_rows.get(record_uuid)
                    shared_eq = shared_rows.get(record_uuid)
                    local_hash = _equipment_sync_hash(local_eq) if local_eq is not None else ""
                    shared_hash = _equipment_sync_hash(shared_eq) if shared_eq is not None else ""
                    last_hash = state_by_uuid.get(record_uuid, "")

                    if not last_hash:
                        if local_hash and shared_hash:
                            if local_hash == shared_hash:
                                _set_record_sync_state(local_conn, record_uuid, local_hash)
                                _resolve_conflict(local_conn, record_uuid)
                            else:
                                _record_conflict(local_conn, record_uuid, local_hash, shared_hash, last_hash)
                                conflicts += 1
                        elif local_hash:
                            if not backed_up_shared:
                                _backup_shared_db(shared_path, backups_dir)
                                backed_up_shared = True
                            _upsert_equipment_by_uuid(shared_conn, local_eq)
                            _set_record_sync_state(local_conn, record_uuid, local_hash)
                            _resolve_conflict(local_conn, record_uuid)
                            pushed += 1
                        elif shared_hash:
                            _upsert_equipment_by_uuid(local_conn, shared_eq)
                            _set_record_sync_state(local_conn, record_uuid, shared_hash)
                            _resolve_conflict(local_conn, record_uuid)
                            pulled += 1
                        continue

                    if local_hash == last_hash and shared_hash == last_hash:
                        continue

                    if local_hash == last_hash:
                        if shared_eq is None:
                            _delete_equipment_by_uuid(local_conn, record_uuid)
                            _clear_record_sync_state(local_conn, record_uuid)
                        else:
                            _upsert_equipment_by_uuid(local_conn, shared_eq)
                            _set_record_sync_state(local_conn, record_uuid, shared_hash)
                        _resolve_conflict(local_conn, record_uuid)
                        pulled += 1
                        continue

                    if shared_hash == last_hash:
                        if not backed_up_shared:
                            _backup_shared_db(shared_path, backups_dir)
                            backed_up_shared = True
                        if local_eq is None:
                            _delete_equipment_by_uuid(shared_conn, record_uuid)
                            _clear_record_sync_state(local_conn, record_uuid)
                        else:
                            _upsert_equipment_by_uuid(shared_conn, local_eq)
                            _set_record_sync_state(local_conn, record_uuid, local_hash)
                        _resolve_conflict(local_conn, record_uuid)
                        pushed += 1
                        continue

                    if local_hash == shared_hash:
                        _set_record_sync_state(local_conn, record_uuid, local_hash)
                        _resolve_conflict(local_conn, record_uuid)
                        continue

                    _record_conflict(local_conn, record_uuid, local_hash, shared_hash, last_hash)
                    conflicts += 1

                local_conn.commit()
                shared_conn.commit()

                if conflicts:
                    message = (
                        f"Synced {pushed} local and {pulled} shared changes. "
                        f"{conflicts} conflict{'s' if conflicts != 1 else ''} need review."
                    )
                elif pushed or pulled:
                    message = f"Synced {pushed} local and {pulled} shared changes."
                else:
                    message = "Already up to date with the shared database."

                return SyncResult(
                    enabled=True,
                    shared_available=True,
                    pushed=pushed,
                    pulled=pulled,
                    conflicts=conflicts,
                    message=message,
                )
            finally:
                shared_conn.close()
    except TimeoutError:
        return SyncResult(enabled=True, shared_available=True, message="Another computer is syncing right now.")
    except OSError:
        return SyncResult(enabled=True, message="Shared workspace is unavailable right now.")


def check_for_update(override_root: Path | None = None) -> UpdateInfo | None:
    """Return update information when a newer release is published on the shared drive."""
    if not update_checks_enabled():
        return None

    manifest_path = _resolve_release_manifest_path(override_root)
    if manifest_path is None or not manifest_path.exists():
        return None

    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

    version = str(data.get("version", "")).strip()
    installer_raw = str(data.get("installer_path", "")).strip()
    if not version or not installer_raw:
        return None

    if _compare_versions(version, getattr(APP_CONFIG, "app_version", "0.0.0")) <= 0:
        return None

    installer_path = Path(installer_raw)
    if not installer_path.is_absolute():
        installer_path = manifest_path.parent / installer_path
    if not installer_path.exists():
        return None

    return UpdateInfo(
        version=version,
        installer_path=installer_path,
        published_at=str(data.get("published_at", "")).strip(),
        notes=str(data.get("notes", "")).strip(),
    )


def sync_interval_ms() -> int:
    """Return the configured automatic sync interval for this app."""
    value = int(getattr(APP_CONFIG, "auto_sync_interval_ms", 300000) or 300000)
    return max(30000, value)


def _resolve_shared_root(override_root: Path | None = None) -> Path | None:
    if override_root is not None:
        return Path(override_root)
    return shared_root_dir()


def _resolve_shared_database_dir(override_root: Path | None, create: bool) -> Path | None:
    if override_root is not None:
        path = Path(override_root) / "shared"
        if create:
            path.mkdir(parents=True, exist_ok=True)
        return path
    return shared_database_dir(create=create)


def _resolve_shared_db_path(override_root: Path | None) -> Path | None:
    if override_root is not None:
        filename = getattr(APP_CONFIG, "shared_db_filename", "").strip()
        if not filename:
            return None
        return Path(override_root) / "shared" / filename
    return shared_db_path()


def _resolve_shared_lock_path(override_root: Path | None) -> Path | None:
    if override_root is not None:
        return Path(override_root) / "shared" / "sync.lock"
    return shared_lock_path()


def _resolve_shared_backup_dir(override_root: Path | None, create: bool) -> Path | None:
    if override_root is not None:
        path = Path(override_root) / "backups"
        if create:
            path.mkdir(parents=True, exist_ok=True)
        return path
    return shared_backup_dir(create=create)


def _resolve_release_manifest_path(override_root: Path | None) -> Path | None:
    if override_root is not None:
        filename = getattr(APP_CONFIG, "release_manifest_filename", "current.json").strip() or "current.json"
        return Path(override_root) / filename
    return shared_release_manifest_path()


def _equipment_count(conn) -> int:
    return conn.execute("SELECT COUNT(*) FROM equipment").fetchone()[0]


def _rebuild_local_sync_state(conn) -> None:
    conn.execute("DELETE FROM record_sync_state")
    rows = get_all_equipment(conn, archived="all")
    for eq in rows:
        if not eq.record_uuid:
            continue
        _set_record_sync_state(conn, eq.record_uuid, _equipment_sync_hash(eq))
    conn.execute("UPDATE sync_conflicts SET resolved=1 WHERE resolved=0")
    conn.commit()


def _load_record_sync_state(conn) -> dict[str, str]:
    rows = conn.execute("SELECT record_uuid, last_synced_hash FROM record_sync_state").fetchall()
    return {
        (row["record_uuid"] if hasattr(row, "keys") else row[0]): (row["last_synced_hash"] if hasattr(row, "keys") else row[1])
        for row in rows
    }


def _set_record_sync_state(conn, record_uuid: str, sync_hash: str) -> None:
    conn.execute(
        """
        INSERT INTO record_sync_state (record_uuid, last_synced_hash, synced_at)
        VALUES (?, ?, datetime('now'))
        ON CONFLICT(record_uuid) DO UPDATE SET
            last_synced_hash=excluded.last_synced_hash,
            synced_at=datetime('now')
        """,
        (record_uuid, sync_hash),
    )


def _clear_record_sync_state(conn, record_uuid: str) -> None:
    conn.execute("DELETE FROM record_sync_state WHERE record_uuid=?", (record_uuid,))


def _record_conflict(conn, record_uuid: str, local_hash: str, shared_hash: str, last_synced_hash: str) -> None:
    summary = f"Both local and shared versions changed for record {record_uuid}."
    existing = conn.execute(
        """
        SELECT id
        FROM sync_conflicts
        WHERE record_uuid=? AND local_hash=? AND shared_hash=? AND last_synced_hash=? AND resolved=0
        """,
        (record_uuid, local_hash, shared_hash, last_synced_hash),
    ).fetchone()
    if existing is not None:
        return
    conn.execute(
        """
        INSERT INTO sync_conflicts (record_uuid, local_hash, shared_hash, last_synced_hash, summary)
        VALUES (?, ?, ?, ?, ?)
        """,
        (record_uuid, local_hash, shared_hash, last_synced_hash, summary),
    )


def _resolve_conflict(conn, record_uuid: str) -> None:
    conn.execute(
        "UPDATE sync_conflicts SET resolved=1 WHERE record_uuid=? AND resolved=0",
        (record_uuid,),
    )


def _equipment_sync_hash(eq: Equipment | None) -> str:
    if eq is None:
        return ""
    payload = {
        field: getattr(eq, field)
        for field in _SYNC_HASH_FIELDS
    }
    raw = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _upsert_equipment_by_uuid(conn, eq: Equipment | None) -> None:
    if eq is None:
        return

    conn.execute(
        """
        INSERT INTO equipment (
            record_uuid, asset_number, serial_number, manufacturer, manufacturer_raw,
            model, description, qty,
            location, assigned_to, ownership_type, rental_vendor, rental_cost_monthly,
            calibration_status, last_calibration_date, calibration_due_date,
            calibration_vendor, calibration_cost,
            lifecycle_status, working_status, condition,
            acquired_date, estimated_age_years, age_basis,
            verified_in_survey, blue_dot_ref,
            project_name, picture_path, links, notes, manual_entry, is_archived, source_refs,
            created_at, updated_at
        ) VALUES (
            ?, ?, ?, ?, ?,
            ?, ?, ?,
            ?, ?, ?, ?, ?,
            ?, ?, ?,
            ?, ?,
            ?, ?, ?,
            ?, ?, ?,
            ?, ?,
            ?, ?, ?, ?, ?, ?, ?,
            ?, ?
        )
        ON CONFLICT(record_uuid) DO UPDATE SET
            asset_number=excluded.asset_number,
            serial_number=excluded.serial_number,
            manufacturer=excluded.manufacturer,
            manufacturer_raw=excluded.manufacturer_raw,
            model=excluded.model,
            description=excluded.description,
            qty=excluded.qty,
            location=excluded.location,
            assigned_to=excluded.assigned_to,
            ownership_type=excluded.ownership_type,
            rental_vendor=excluded.rental_vendor,
            rental_cost_monthly=excluded.rental_cost_monthly,
            calibration_status=excluded.calibration_status,
            last_calibration_date=excluded.last_calibration_date,
            calibration_due_date=excluded.calibration_due_date,
            calibration_vendor=excluded.calibration_vendor,
            calibration_cost=excluded.calibration_cost,
            lifecycle_status=excluded.lifecycle_status,
            working_status=excluded.working_status,
            condition=excluded.condition,
            acquired_date=excluded.acquired_date,
            estimated_age_years=excluded.estimated_age_years,
            age_basis=excluded.age_basis,
            verified_in_survey=excluded.verified_in_survey,
            blue_dot_ref=excluded.blue_dot_ref,
            project_name=excluded.project_name,
            picture_path=excluded.picture_path,
            links=excluded.links,
            notes=excluded.notes,
            manual_entry=excluded.manual_entry,
            is_archived=excluded.is_archived,
            source_refs=excluded.source_refs,
            created_at=excluded.created_at,
            updated_at=excluded.updated_at
        """,
        (
            eq.record_uuid,
            eq.asset_number,
            eq.serial_number,
            eq.manufacturer,
            eq.manufacturer_raw,
            eq.model,
            eq.description,
            eq.qty,
            eq.location,
            eq.assigned_to,
            eq.ownership_type,
            eq.rental_vendor,
            eq.rental_cost_monthly,
            eq.calibration_status,
            eq.last_calibration_date,
            eq.calibration_due_date,
            eq.calibration_vendor,
            eq.calibration_cost,
            eq.lifecycle_status,
            eq.working_status,
            eq.condition,
            eq.acquired_date,
            eq.estimated_age_years,
            eq.age_basis,
            1 if eq.verified_in_survey else 0,
            eq.blue_dot_ref,
            eq.project_name,
            eq.picture_path,
            eq.links,
            eq.notes,
            1 if eq.manual_entry else 0,
            1 if eq.is_archived else 0,
            eq.source_refs,
            eq.created_at,
            eq.updated_at,
        ),
    )
    row = conn.execute(
        "SELECT record_id FROM equipment WHERE record_uuid=?",
        (eq.record_uuid,),
    ).fetchone()
    if row is None:
        return
    record_id = row["record_id"] if hasattr(row, "keys") else row[0]
    conn.execute("DELETE FROM equipment_search WHERE record_id=?", (record_id,))
    conn.execute(
        "INSERT INTO equipment_search (record_id, search_text) VALUES (?, ?)",
        (record_id, _build_equipment_search_text(eq)),
    )


def _delete_equipment_by_uuid(conn, record_uuid: str) -> None:
    row = conn.execute(
        "SELECT record_id FROM equipment WHERE record_uuid=?",
        (record_uuid,),
    ).fetchone()
    if row is None:
        return
    record_id = row["record_id"] if hasattr(row, "keys") else row[0]
    conn.execute("DELETE FROM equipment WHERE record_uuid=?", (record_uuid,))
    conn.execute("DELETE FROM equipment_search WHERE record_id=?", (record_id,))


def _backup_shared_db(shared_path: Path, backups_dir: Path) -> None:
    if not shared_path.exists():
        return
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"{shared_path.stem}_{timestamp}{shared_path.suffix}"
    shutil.copy2(shared_path, backups_dir / backup_name)


def _compare_versions(left: str, right: str) -> int:
    left_parts = _version_parts(left)
    right_parts = _version_parts(right)
    width = max(len(left_parts), len(right_parts))
    padded_left = left_parts + (0,) * (width - len(left_parts))
    padded_right = right_parts + (0,) * (width - len(right_parts))
    if padded_left == padded_right:
        return 0
    return 1 if padded_left > padded_right else -1


def _version_parts(value: str) -> tuple[int, ...]:
    parts = []
    for token in value.split("."):
        digits = "".join(ch for ch in token if ch.isdigit())
        parts.append(int(digits or 0))
    return tuple(parts)


@contextmanager
def _shared_lock(lock_path: Path):
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "host": socket.gethostname(),
        "pid": os.getpid(),
        "time": datetime.now().isoformat(timespec="seconds"),
    }

    while True:
        try:
            fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            break
        except FileExistsError as exc:
            try:
                age = datetime.now().timestamp() - lock_path.stat().st_mtime
            except OSError:
                raise TimeoutError("Shared sync lock is busy.") from exc
            if age > _LOCK_STALE_SECONDS:
                try:
                    lock_path.unlink()
                    continue
                except OSError as unlink_exc:
                    raise TimeoutError("Shared sync lock is busy.") from unlink_exc
            raise TimeoutError("Shared sync lock is busy.") from exc

    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle)
        yield
    finally:
        try:
            lock_path.unlink()
        except FileNotFoundError:
            pass

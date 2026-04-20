"""Release-manifest helpers kept separate from shared data sync behavior."""

from __future__ import annotations

import json
from pathlib import Path

from app_config import APP_CONFIG
from Code.sync.contracts import UpdateInfo
from Code.utils.runtime_paths import shared_release_manifest_path as runtime_shared_release_manifest_path


def update_checks_enabled() -> bool:
    """Return whether this app variant should look for newer releases."""
    return bool(getattr(APP_CONFIG, "enable_update_checks", False))


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


def _resolve_release_manifest_path(override_root: Path | None) -> Path | None:
    if override_root is not None:
        filename = getattr(APP_CONFIG, "release_manifest_filename", "current.json").strip() or "current.json"
        return override_root / filename
    return runtime_shared_release_manifest_path()


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

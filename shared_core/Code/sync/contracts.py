"""Structured result objects for the shared-first sync runtime."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class SyncResult:
    enabled: bool = False
    shared_available: bool = False
    busy: bool = False
    queued: int = 0
    flushed: int = 0
    superseded: int = 0
    pulled: int = 0
    initialized: str = ""
    pushed: int = 0
    conflicts: int = 0
    local_revision: str = ""
    shared_revision: str = ""
    message: str = ""


@dataclass(frozen=True, slots=True)
class RevisionInfo:
    enabled: bool = False
    shared_available: bool = False
    busy: bool = False
    local_revision: str = ""
    shared_revision: str = ""
    local_dirty: bool = False
    needs_sync: bool = False
    queued: int = 0
    message: str = ""


@dataclass(frozen=True, slots=True)
class SharedStatus:
    enabled: bool = False
    shared_available: bool = False
    busy: bool = False
    queued: int = 0
    local_revision: str = ""
    shared_revision: str = ""
    message: str = ""


@dataclass(frozen=True, slots=True)
class UpdateInfo:
    version: str
    installer_path: Path
    published_at: str = ""
    notes: str = ""

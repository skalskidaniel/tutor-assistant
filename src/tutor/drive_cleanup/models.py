from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class DriveFolder:
    id: str
    name: str
    is_shortcut: bool = False


@dataclass(frozen=True)
class DriveFile:
    id: str
    name: str
    created_time: datetime


@dataclass(frozen=True)
class DriveCleanupResult:
    scanned_students: int
    deleted_files: int
    renamed_files: int

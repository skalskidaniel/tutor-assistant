from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from tutor.drive_cleanup import DriveCleanupService  # pyright: ignore[reportMissingImports]
from tutor.drive_cleanup.models import (  # pyright: ignore[reportMissingImports]
    DriveFile,
    DriveFolder,
)


@dataclass(frozen=True)
class RenameCall:
    file_id: str
    new_name: str


class FakeDriveCleanupProvider:
    def __init__(self) -> None:
        now = datetime.now(timezone.utc)
        self._student_folders = [
            DriveFolder(id="student-1", name="jan-kowalski"),
            DriveFolder(id="student-2", name="anna-nowak"),
        ]
        self._children = {
            "student-1": [
                DriveFolder(id="student-1-homework", name="Zadania domowe"),
                DriveFolder(id="student-1-notes", name="notatki"),
                DriveFolder(id="student-1-shortcut", name="Matura", is_shortcut=True),
            ],
            "student-1-homework": [
                DriveFolder(id="student-1-homework-archive", name="stare")
            ],
            "student-1-notes": [
                DriveFolder(id="student-1-notes-extra", name="powtorki")
            ],
            "student-2": [DriveFolder(id="student-2-notes", name="Notatki")],
            "student-2-notes": [],
            "student-1-homework-archive": [],
            "student-1-notes-extra": [],
            "student-1-shortcut": [
                DriveFolder(id="shortcut-homework", name="zadania-domowe")
            ],
            "shortcut-homework": [],
        }
        self._files = {
            "student-1-homework": [
                DriveFile(
                    id="old-homework",
                    name="stare zadanie.pdf",
                    created_time=now - timedelta(days=61),
                ),
                DriveFile(
                    id="fresh-homework",
                    name="nowe-zadanie.pdf",
                    created_time=now - timedelta(days=15),
                ),
            ],
            "student-1-homework-archive": [
                DriveFile(
                    id="old-homework-archive",
                    name="bardzo stare zadanie.pdf",
                    created_time=now - timedelta(days=120),
                )
            ],
            "student-1-notes": [
                DriveFile(
                    id="notes-1",
                    name="Funkcja kwadratowa.pdf",
                    created_time=now - timedelta(days=1),
                ),
                DriveFile(
                    id="notes-2",
                    name="planimetria.pdf",
                    created_time=now - timedelta(days=1),
                ),
                DriveFile(
                    id="notes-3",
                    name="Wzory Viète.PDF",
                    created_time=now - timedelta(days=1),
                ),
            ],
            "student-1-notes-extra": [
                DriveFile(
                    id="notes-5",
                    name="Trygonometria 2.PDF",
                    created_time=now - timedelta(days=1),
                )
            ],
            "student-2-notes": [
                DriveFile(
                    id="notes-4",
                    name="Geometria analityczna.docx",
                    created_time=now - timedelta(days=1),
                )
            ],
            "shortcut-homework": [
                DriveFile(
                    id="shortcut-old-homework",
                    name="z-linku.pdf",
                    created_time=now - timedelta(days=400),
                )
            ],
        }
        self.deleted_file_ids: list[str] = []
        self.rename_calls: list[RenameCall] = []

    def list_student_folders(self) -> list[DriveFolder]:
        return list(self._student_folders)

    def list_child_folders(self, *, parent_folder_id: str) -> list[DriveFolder]:
        return list(self._children.get(parent_folder_id, []))

    def list_files(self, *, folder_id: str) -> list[DriveFile]:
        return list(self._files.get(folder_id, []))

    def delete_file(self, *, file_id: str) -> None:
        self.deleted_file_ids.append(file_id)

    def rename_file(self, *, file_id: str, new_name: str) -> None:
        self.rename_calls.append(RenameCall(file_id=file_id, new_name=new_name))


def test_drive_cleanup_removes_old_homework_and_normalizes_notes() -> None:
    provider = FakeDriveCleanupProvider()
    service = DriveCleanupService(provider=provider)

    result = service.cleanup()

    assert result.scanned_students == 2
    assert result.deleted_files == 2
    assert result.renamed_files == 4
    assert provider.deleted_file_ids == ["old-homework", "old-homework-archive"]
    assert provider.rename_calls == [
        RenameCall(file_id="notes-1", new_name="funkcja-kwadratowa.pdf"),
        RenameCall(file_id="notes-3", new_name="wzory-viete.pdf"),
        RenameCall(file_id="notes-5", new_name="trygonometria-2.pdf"),
        RenameCall(file_id="notes-4", new_name="geometria-analityczna.docx"),
    ]

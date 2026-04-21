from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import PurePath

from tutor.core import slugify

from .models import DriveCleanupResult, DriveFile, DriveFolder
from .providers import DriveCleanupProvider


class DriveCleanupService:
    def __init__(self, provider: DriveCleanupProvider) -> None:
        self._provider = provider

    def cleanup(self) -> DriveCleanupResult:
        students = self._provider.list_student_folders()
        cutoff = datetime.now(timezone.utc) - timedelta(days=60)

        deleted_files = 0
        renamed_files = 0

        for student in students:
            homework_folders, notes_folders = self._find_target_folders(student.id)

            for homework_folder in homework_folders:
                deleted_files += self._cleanup_homework_tree(
                    root_folder_id=homework_folder.id,
                    cutoff=cutoff,
                )

            for notes_folder in notes_folders:
                renamed_files += self._normalize_notes_tree(
                    root_folder_id=notes_folder.id
                )

        return DriveCleanupResult(
            scanned_students=len(students),
            deleted_files=deleted_files,
            renamed_files=renamed_files,
        )

    def _delete_old_homework(self, files: list[DriveFile], *, cutoff: datetime) -> int:
        deleted = 0
        for file in files:
            if file.created_time < cutoff:
                self._provider.delete_file(file_id=file.id)
                deleted += 1
        return deleted

    def _rename_notes(self, files: list[DriveFile]) -> int:
        renamed = 0
        for file in files:
            normalized_name = _normalized_filename(file.name)
            if normalized_name != file.name:
                self._provider.rename_file(file_id=file.id, new_name=normalized_name)
                renamed += 1
        return renamed

    def _cleanup_homework_tree(self, *, root_folder_id: str, cutoff: datetime) -> int:
        deleted = 0
        for folder_id in self._walk_folder_tree(root_folder_id):
            files = self._provider.list_files(folder_id=folder_id)
            deleted += self._delete_old_homework(files, cutoff=cutoff)
        return deleted

    def _normalize_notes_tree(self, *, root_folder_id: str) -> int:
        renamed = 0
        for folder_id in self._walk_folder_tree(root_folder_id):
            files = self._provider.list_files(folder_id=folder_id)
            renamed += self._rename_notes(files)
        return renamed

    def _find_target_folders(
        self, student_folder_id: str
    ) -> tuple[list[DriveFolder], list[DriveFolder]]:
        homework_folders: list[DriveFolder] = []
        notes_folders: list[DriveFolder] = []
        queue = [student_folder_id]
        visited: set[str] = set()

        while queue:
            folder_id = queue.pop(0)
            if folder_id in visited:
                continue
            visited.add(folder_id)

            for child in self._provider.list_child_folders(parent_folder_id=folder_id):
                if child.is_shortcut:
                    continue
                normalized_name = _normalize_folder_name(child.name)
                if normalized_name == "zadania-domowe":
                    homework_folders.append(child)
                    continue
                if normalized_name == "notatki":
                    notes_folders.append(child)
                    continue
                queue.append(child.id)

        return homework_folders, notes_folders

    def _walk_folder_tree(self, root_folder_id: str) -> list[str]:
        queue = [root_folder_id]
        visited: set[str] = set()
        folder_ids: list[str] = []

        while queue:
            folder_id = queue.pop(0)
            if folder_id in visited:
                continue
            visited.add(folder_id)
            folder_ids.append(folder_id)

            for child in self._provider.list_child_folders(parent_folder_id=folder_id):
                if child.is_shortcut:
                    continue
                queue.append(child.id)

        return folder_ids


def _normalized_filename(filename: str) -> str:
    suffix = PurePath(filename).suffix
    stem = filename[: -len(suffix)] if suffix else filename
    normalized_stem = slugify(stem)
    normalized_suffix = suffix.lower()
    return f"{normalized_stem}{normalized_suffix}"


def _normalize_folder_name(value: str) -> str:
    return slugify(value).replace("_", "-")

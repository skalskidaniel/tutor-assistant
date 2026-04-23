from __future__ import annotations

from pathlib import Path
import os
from typing import Protocol

from googleapiclient.errors import HttpError

from tutor.core import format_http_error
from tutor.core.utils import resolve_required_path
from tutor.drive import build_drive_service, parse_google_timestamp

from .models import DriveFile, DriveFolder


class DriveCleanupProvider(Protocol):
    def list_student_folders(self) -> list[DriveFolder]: ...

    def list_child_folders(self, *, parent_folder_id: str) -> list[DriveFolder]: ...

    def list_files(self, *, folder_id: str) -> list[DriveFile]: ...

    def delete_file(self, *, file_id: str) -> None: ...

    def rename_file(self, *, file_id: str, new_name: str) -> None: ...


class GoogleDriveCleanupProvider:

    def __init__(
        self,
        *,
        credentials_path: str | Path | None = "secrets/credentials.json",
        token_path: str | Path | None = "secrets/token.json",
        student_notes_folder_id: str | None = None,
    ) -> None:
        self._credentials_path = resolve_required_path(
            explicit_path=credentials_path,
            env_var_name="GOOGLE_CREDENTIALS_PATH"
        )
        self._token_path = resolve_required_path(
            explicit_path=token_path,
            env_var_name="GOOGLE_TOKEN_PATH"
        )
        self._parent_folder_id = student_notes_folder_id or os.getenv(
            "GOOGLE_DRIVE_STUDENT_NOTES_FOLDER_ID"
        )
        if not self._parent_folder_id:
            raise ValueError(
                "Missing GOOGLE_DRIVE_STUDENT_NOTES_FOLDER_ID. "
                "You may use --student-notes-folder-id."
            )

    def list_student_folders(self) -> list[DriveFolder]:
        query = (
            f"'{self._parent_folder_id}' in parents "
            "and (mimeType='application/vnd.google-apps.folder' "
            "or mimeType='application/vnd.google-apps.shortcut') and trashed=false"
        )
        return self._list_folders(query=query)

    def list_child_folders(self, *, parent_folder_id: str) -> list[DriveFolder]:
        query = (
            f"'{parent_folder_id}' in parents "
            "and (mimeType='application/vnd.google-apps.folder' "
            "or mimeType='application/vnd.google-apps.shortcut') and trashed=false"
        )
        return self._list_folders(query=query)

    def list_files(self, *, folder_id: str) -> list[DriveFile]:
        drive_service = self._build_drive_service()
        query = (
            f"'{folder_id}' in parents and "
            "mimeType!='application/vnd.google-apps.folder' and trashed=false"
        )

        files: list[DriveFile] = []
        page_token: str | None = None
        try:
            while True:
                response = (
                    drive_service.files()
                    .list(
                        q=query,
                        fields="nextPageToken, files(id, name, createdTime)",
                        pageToken=page_token,
                    )
                    .execute()
                )
                for item in response.get("files", []):
                    file_id = item.get("id")
                    name = item.get("name")
                    created_time_raw = item.get("createdTime")
                    if (
                        isinstance(file_id, str)
                        and isinstance(name, str)
                        and isinstance(created_time_raw, str)
                    ):
                        files.append(
                            DriveFile(
                                id=file_id,
                                name=name,
                                created_time=parse_google_timestamp(created_time_raw),
                            )
                        )
                page_token = response.get("nextPageToken")
                if not page_token:
                    break
        except HttpError as exc:
            raise RuntimeError(
                "Error downloading files list from Google Drive. "
                f"Details: {format_http_error(exc)}"
            ) from exc

        return files

    def delete_file(self, *, file_id: str) -> None:
        drive_service = self._build_drive_service()
        try:
            drive_service.files().delete(fileId=file_id).execute()
        except HttpError as exc:
            raise RuntimeError(
                f"Error deleting file {file_id}. Details: {format_http_error(exc)}"
            ) from exc

    def rename_file(self, *, file_id: str, new_name: str) -> None:
        drive_service = self._build_drive_service()
        try:
            drive_service.files().update(
                fileId=file_id, body={"name": new_name}
            ).execute()
        except HttpError as exc:
            raise RuntimeError(
                f"Error renaming file {file_id}. Details: {format_http_error(exc)}"
            ) from exc

    def _list_folders(self, *, query: str) -> list[DriveFolder]:
        drive_service = self._build_drive_service()
        folders: list[DriveFolder] = []
        page_token: str | None = None
        try:
            while True:
                response = (
                    drive_service.files()
                    .list(
                        q=query,
                        fields="nextPageToken, files(id, name, mimeType, shortcutDetails)",
                        pageToken=page_token,
                    )
                    .execute()
                )
                for item in response.get("files", []):
                    folder_id = item.get("id")
                    name = item.get("name")
                    mime_type = item.get("mimeType")
                    shortcut_details = item.get("shortcutDetails")
                    is_shortcut = (
                        mime_type == "application/vnd.google-apps.shortcut"
                        or isinstance(shortcut_details, dict)
                    )
                    if isinstance(folder_id, str) and isinstance(name, str):
                        folders.append(
                            DriveFolder(
                                id=folder_id,
                                name=name,
                                is_shortcut=is_shortcut,
                            )
                        )

                page_token = response.get("nextPageToken")
                if not page_token:
                    break
        except HttpError as exc:
            raise RuntimeError(
                "Error downloading folders list from Google Drive. "
                f"Details: {format_http_error(exc)}"
            ) from exc

        return folders

    def _build_drive_service(self):
        return build_drive_service(
            credentials_path=self._credentials_path,
            token_path=self._token_path,
        )

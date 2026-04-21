from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
import os
from typing import Protocol
from uuid import uuid4
from zoneinfo import ZoneInfo

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from tutor.core import GOOGLE_ONBOARDING_SCOPES, load_google_credentials, resolve_required_path, format_http_error

from .models import MeetingSchedule, Student

WEEKDAY_TO_RRULE = {0: "MO", 1: "TU", 2: "WE", 3: "TH", 4: "FR", 5: "SA", 6: "SU"}


class MeetProvider(Protocol):
    def create_personal_meeting(
        self, student: Student, schedule: MeetingSchedule
    ) -> str:
        ...


class DriveProvider(Protocol):
    def create_student_workspace(self, student: Student) -> str:
        ...


class InMemoryMeetProvider:
    """Used only inside integration tests"""
    def create_personal_meeting(
        self, student: Student, schedule: MeetingSchedule
    ) -> str:
        token = f"{student.folder_slug}-{uuid4().hex[:8]}"
        return f"https://meet.google.com/{token}"


class InMemoryDriveProvider:
    """Used only inside integration tests"""

    def create_student_workspace(self, student: Student) -> str:
        return f"https://drive.google.com/drive/folders/{student.folder_slug}-{uuid4().hex[:10]}"


class GoogleMeetProvider:

    def __init__(
        self,
        *,
        credentials_path: str | Path | None = None,
        token_path: str | Path | None = None,
        calendar_id: str = "primary",
        timezone: str = "Europe/Warsaw",
        meeting_duration_minutes: int = 60,
    ) -> None:
        self._credentials_path = resolve_required_path(
            explicit_path=credentials_path,
            env_var_name="GOOGLE_CREDENTIALS_PATH",
        )
        self._token_path = resolve_required_path(
            explicit_path=token_path,
            env_var_name="GOOGLE_TOKEN_PATH",
        )
        self._calendar_id = calendar_id
        self._timezone = timezone
        self._meeting_duration_minutes = meeting_duration_minutes
        self._last_created_event_id: str | None = None

    def create_personal_meeting(
        self, student: Student, schedule: MeetingSchedule
    ) -> str:
        credentials = load_google_credentials(
            credentials_path=self._credentials_path,
            token_path=self._token_path,
            scopes=GOOGLE_ONBOARDING_SCOPES,
        )
        calendar_service = build("calendar", "v3", credentials=credentials)

        start_at = self._next_meeting_datetime(schedule)
        end_at = start_at + timedelta(minutes=self._meeting_duration_minutes)
        event_payload: dict[str, object] = {
            "summary": f"{student.full_name}",
            "description": (
                "Automatycznie utworzone spotkanie.\n"
                f"Telefon ucznia: {student.phone}"
            ),
            "start": {"dateTime": start_at.isoformat(), "timeZone": self._timezone},
            "end": {"dateTime": end_at.isoformat(), "timeZone": self._timezone},
            "attendees": [{"email": student.email}],
            "conferenceData": {
                "createRequest": {
                    "requestId": uuid4().hex,
                    "conferenceSolutionKey": {"type": "hangoutsMeet"},
                }
            },
        }
        recurrence = self._build_recurrence(schedule)
        if recurrence:
            event_payload["recurrence"] = recurrence

        try:
            created = (
                calendar_service.events()
                .insert(
                    calendarId=self._calendar_id,
                    body=event_payload,
                    conferenceDataVersion=1,
                    sendUpdates="none",
                )
                .execute()
            )
            event_id = created.get("id")
            if isinstance(event_id, str) and event_id:
                self._last_created_event_id = event_id
        except HttpError as exc:
            raise RuntimeError(
                f"Error creating google-meet url. Details: {format_http_error(exc)}"
            ) from exc

        conference_data = created.get("conferenceData", {})
        for entry in conference_data.get("entryPoints", []):
            uri = entry.get("uri")
            if isinstance(uri, str) and uri.startswith("https://meet.google.com/"):
                return uri

        raise RuntimeError("Google calendar did not return meeting url")

    def delete_last_created_meeting(self) -> None:
        if self._last_created_event_id is None:
            return

        credentials = load_google_credentials(
            credentials_path=self._credentials_path,
            token_path=self._token_path,
            scopes=GOOGLE_ONBOARDING_SCOPES,
        )
        calendar_service = build("calendar", "v3", credentials=credentials)
        try:
            (
                calendar_service.events()
                .delete(
                    calendarId=self._calendar_id, eventId=self._last_created_event_id
                )
                .execute()
            )
        except HttpError as exc:
            raise RuntimeError(
                f"Error deleting test meeting. Details: {format_http_error(exc)}"
            ) from exc
        finally:
            self._last_created_event_id = None

    def _next_meeting_datetime(self, schedule: MeetingSchedule) -> datetime:
        meeting_date = schedule.meeting_date
        return datetime(
            year=meeting_date.year,
            month=meeting_date.month,
            day=meeting_date.day,
            hour=schedule.hour,
            minute=schedule.minute,
            second=0,
            microsecond=0,
            tzinfo=ZoneInfo(self._timezone),
        )

    def _build_recurrence(self, schedule: MeetingSchedule) -> list[str]:
        if schedule.recurrence == "none":
            return []

        rule = "RRULE:FREQ=WEEKLY"
        if schedule.recurrence == "biweekly":
            rule = f"{rule};INTERVAL=2"

        byday = WEEKDAY_TO_RRULE[schedule.weekday]
        rule = f"{rule};BYDAY={byday}"
        if schedule.occurrences is not None:
            rule = f"{rule};COUNT={schedule.occurrences}"

        return [rule]


class GoogleDriveProvider:

    def __init__(
        self,
        *,
        credentials_path: str | Path | None = None,
        token_path: str | Path | None = None,
        parent_folder_id: str | None = None,
    ) -> None:
        self._credentials_path = resolve_required_path(
            explicit_path=credentials_path,
            env_var_name="GOOGLE_CREDENTIALS_PATH",
        )
        self._token_path = resolve_required_path(
            explicit_path=token_path,
            env_var_name="GOOGLE_TOKEN_PATH",
        )
        self._parent_folder_id = parent_folder_id or os.getenv(
            "GOOGLE_DRIVE_PARENT_FOLDER_ID"
        )
        self._last_created_workspace_id: str | None = None

    def create_student_workspace(self, student: Student) -> str:
        credentials = load_google_credentials(
            credentials_path=self._credentials_path,
            token_path=self._token_path,
            scopes=GOOGLE_ONBOARDING_SCOPES,
        )
        drive_service = build("drive", "v3", credentials=credentials)

        try:
            root_id, root_url = self._create_folder(
                drive_service=drive_service,
                name=student.folder_slug,
                parent_id=self._parent_folder_id,
            )
            self._last_created_workspace_id = root_id
            self._create_folder(
                drive_service=drive_service,
                name="zadania-domowe",
                parent_id=root_id,
            )
            self._create_folder(
                drive_service=drive_service,
                name="notatki",
                parent_id=root_id,
            )
            self._share_folder(
                drive_service=drive_service,
                folder_id=root_id,
            )
        except HttpError as exc:
            raise RuntimeError(
                f"Error creating google drive url. Details: {format_http_error(exc)}"
            ) from exc

        if root_url:
            return root_url

        fallback = (
            drive_service.files()
            .get(fileId=root_id, fields="webViewLink")
            .execute()
            .get("webViewLink")
        )
        if isinstance(fallback, str) and fallback:
            return fallback

        raise RuntimeError(
            "Folder was created, but an error occurred sharing it."
        )

    def delete_last_created_workspace(self) -> None:
        if self._last_created_workspace_id is None:
            return

        credentials = load_google_credentials(
            credentials_path=self._credentials_path,
            token_path=self._token_path,
            scopes=GOOGLE_ONBOARDING_SCOPES,
        )
        drive_service = build("drive", "v3", credentials=credentials)
        try:
            self._delete_folder_tree(
                drive_service=drive_service,
                folder_id=self._last_created_workspace_id,
            )
        except HttpError as exc:
            raise RuntimeError(
                f"Error deleting test google drive folder. Details {format_http_error(exc)}"
            ) from exc
        finally:
            self._last_created_workspace_id = None

    @staticmethod
    def _create_folder(
        *,
        drive_service,
        name: str,
        parent_id: str | None,
    ) -> tuple[str, str | None]:
        metadata: dict[str, object] = {
            "name": name,
            "mimeType": "application/vnd.google-apps.folder",
        }
        if parent_id:
            metadata["parents"] = [parent_id]

        created = (
            drive_service.files()
            .create(
                body=metadata,
                fields="id, webViewLink",
            )
            .execute()
        )

        folder_id = created.get("id")
        if not isinstance(folder_id, str) or not folder_id:
            raise RuntimeError("Google Drive API did not return folder id.")

        raw_url = created.get("webViewLink")
        folder_url = raw_url if isinstance(raw_url, str) and raw_url else None
        return folder_id, folder_url

    @staticmethod
    def _share_folder(*, drive_service, folder_id: str) -> None:
        drive_service.permissions().create(
            fileId=folder_id,
            body={"type": "anyone", "role": "reader", "allowFileDiscovery": False},
            sendNotificationEmail=False,
        ).execute()

    @classmethod
    def _delete_folder_tree(cls, *, drive_service, folder_id: str) -> None:
        query = f"'{folder_id}' in parents and trashed=false"
        response = (
            drive_service.files()
            .list(
                q=query,
                fields="files(id, mimeType)",
            )
            .execute()
        )
        for item in response.get("files", []):
            child_id = item.get("id")
            mime_type = item.get("mimeType")
            if not isinstance(child_id, str):
                continue
            if mime_type == "application/vnd.google-apps.folder":
                cls._delete_folder_tree(drive_service=drive_service, folder_id=child_id)
                continue
            drive_service.files().delete(fileId=child_id).execute()

        drive_service.files().delete(fileId=folder_id).execute()
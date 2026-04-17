"""Providers and integrations for onboarding flow."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
import os
from typing import Protocol, cast
from uuid import uuid4
from zoneinfo import ZoneInfo

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from .models import MeetingSchedule, NewStudentRequest

CALENDAR_SCOPES = ("https://www.googleapis.com/auth/calendar.events",)
DRIVE_SCOPES = ("https://www.googleapis.com/auth/drive",)
GOOGLE_ONBOARDING_SCOPES = CALENDAR_SCOPES + DRIVE_SCOPES
WEEKDAY_TO_RRULE = {0: "MO", 1: "TU", 2: "WE", 3: "TH", 4: "FR", 5: "SA", 6: "SU"}


class MeetProvider(Protocol):
    def create_personal_meeting(self, student: NewStudentRequest) -> str:
        """Tworzy spersonalizowany link Google Meet dla ucznia."""
        ...


class DriveProvider(Protocol):
    def create_student_workspace(self, student: NewStudentRequest) -> str:
        """Tworzy strukture katalogow ucznia i zwraca shared_url)."""
        ...


class InMemoryMeetProvider:
    """Prosta implementacja testowa - bez polaczenia z Google API."""

    def create_personal_meeting(self, student: NewStudentRequest) -> str:
        token = f"{student.folder_slug}-{uuid4().hex[:8]}"
        return f"https://meet.google.com/{token}"


class InMemoryDriveProvider:
    """Prosta implementacja testowa - zwraca docelowa strukture katalogow."""

    def create_student_workspace(self, student: NewStudentRequest) -> str:
        return f"https://drive.google.com/drive/folders/{student.folder_slug}-{uuid4().hex[:10]}"


class GoogleMeetProvider:
    """Provider tworzacy link Google Meet przez Google Calendar API."""

    def __init__(
        self,
        *,
        credentials_path: str | Path | None = None,
        token_path: str | Path | None = None,
        calendar_id: str = "primary",
        timezone: str = "Europe/Warsaw",
        meeting_duration_minutes: int = 60,
        schedule: MeetingSchedule | None = None,
    ) -> None:
        self._credentials_path = Path(
            credentials_path or os.getenv("GOOGLE_CREDENTIALS_PATH", "credentials.json")
        )
        self._token_path = Path(
            token_path or os.getenv("GOOGLE_TOKEN_PATH", "token.json")
        )
        self._calendar_id = calendar_id
        self._timezone = timezone
        self._meeting_duration_minutes = meeting_duration_minutes
        tomorrow = datetime.now(ZoneInfo(timezone)).date() + timedelta(days=1)
        self._schedule = schedule or MeetingSchedule(
            meeting_date=tomorrow,
            hour=18,
            minute=0,
            recurrence="weekly",
        )
        self._last_created_event_id: str | None = None

    def create_personal_meeting(self, student: NewStudentRequest) -> str:
        credentials = _load_google_credentials(
            credentials_path=self._credentials_path,
            token_path=self._token_path,
            scopes=GOOGLE_ONBOARDING_SCOPES,
        )
        calendar_service = build("calendar", "v3", credentials=credentials)

        start_at = self._next_meeting_datetime()
        end_at = start_at + timedelta(minutes=self._meeting_duration_minutes)
        event_payload: dict[str, object] = {
            "summary": f"{student.full_name}",
            "description": (
                "Automatycznie utworzone spotkanie onboardingowe.\n"
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
        recurrence = self._build_recurrence()
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
                f"Nie udalo sie utworzyc linku Google Meet. Szczegoly: {_format_http_error(exc)}"
            ) from exc

        conference_data = created.get("conferenceData", {})
        for entry in conference_data.get("entryPoints", []):
            uri = entry.get("uri")
            if isinstance(uri, str) and uri.startswith("https://meet.google.com/"):
                return uri

        raise RuntimeError("Google Calendar nie zwrocil linku Google Meet.")

    def delete_last_created_meeting(self) -> None:
        if self._last_created_event_id is None:
            return

        credentials = _load_google_credentials(
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
                f"Nie udalo sie usunac testowego spotkania. Szczegoly: {_format_http_error(exc)}"
            ) from exc
        finally:
            self._last_created_event_id = None

    def _next_meeting_datetime(self) -> datetime:
        meeting_date = self._schedule.meeting_date
        return datetime(
            year=meeting_date.year,
            month=meeting_date.month,
            day=meeting_date.day,
            hour=self._schedule.hour,
            minute=self._schedule.minute,
            second=0,
            microsecond=0,
            tzinfo=ZoneInfo(self._timezone),
        )

    def _build_recurrence(self) -> list[str]:
        if self._schedule.recurrence == "none":
            return []

        rule = "RRULE:FREQ=WEEKLY"
        if self._schedule.recurrence == "biweekly":
            rule = f"{rule};INTERVAL=2"

        byday = WEEKDAY_TO_RRULE[self._schedule.weekday]
        rule = f"{rule};BYDAY={byday}"
        if self._schedule.occurrences is not None:
            rule = f"{rule};COUNT={self._schedule.occurrences}"

        return [rule]


class GoogleDriveProvider:
    """Provider tworzacy folder ucznia i udostepniajacy go przez Drive API."""

    def __init__(
        self,
        *,
        credentials_path: str | Path | None = None,
        token_path: str | Path | None = None,
        parent_folder_id: str | None = None,
    ) -> None:
        self._credentials_path = Path(
            credentials_path or os.getenv("GOOGLE_CREDENTIALS_PATH", "credentials.json")
        )
        self._token_path = Path(
            token_path or os.getenv("GOOGLE_TOKEN_PATH", "token.json")
        )
        self._parent_folder_id = parent_folder_id or os.getenv(
            "GOOGLE_DRIVE_PARENT_FOLDER_ID"
        )

    def create_student_workspace(self, student: NewStudentRequest) -> str:
        credentials = _load_google_credentials(
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
                "Nie udalo sie utworzyc i udostepnic folderu na Google Drive. "
                f"Szczegoly: {_format_http_error(exc)}"
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
            "Folder zostal utworzony, ale nie udalo sie pobrac linku udostepnienia."
        )

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
            raise RuntimeError("Drive API nie zwrocilo identyfikatora folderu.")

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


def _load_google_credentials(
    *,
    credentials_path: Path,
    token_path: Path,
    scopes: tuple[str, ...],
) -> Credentials:
    credentials: Credentials | None = None

    if token_path.exists():
        credentials = cast(
            Credentials,
            Credentials.from_authorized_user_file(str(token_path), scopes),
        )

    if (
        credentials
        and credentials.valid
        and _credentials_cover_scopes(credentials, scopes)
    ):
        return credentials

    if (
        credentials
        and credentials.expired
        and credentials.refresh_token
        and _credentials_cover_scopes(credentials, scopes)
    ):
        credentials.refresh(Request())
    else:
        if not credentials_path.exists():
            raise FileNotFoundError(
                f"Brak pliku credentials: {credentials_path}. "
                "Pobierz go z Google Cloud Console."
            )
        flow = InstalledAppFlow.from_client_secrets_file(str(credentials_path), scopes)
        credentials = cast(Credentials, flow.run_local_server(port=0))

    if credentials is None:
        raise RuntimeError(
            "Nie udalo sie uzyskac poprawnych danych uwierzytelniajacych Google."
        )

    token_path.write_text(credentials.to_json(), encoding="utf-8")
    return credentials


def _credentials_cover_scopes(
    credentials: Credentials, scopes: tuple[str, ...]
) -> bool:
    return credentials.has_scopes(list(scopes))


def _format_http_error(error: HttpError) -> str:
    status = getattr(error.resp, "status", "unknown")
    reason = getattr(error, "reason", None)
    if isinstance(reason, str) and reason:
        return f"HTTP {status}: {reason}"
    return f"HTTP {status}: {error}"

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path
import re
from typing import Protocol

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from .auth import (
    GOOGLE_CALENDAR_DRIVE_SCOPES,
    GOOGLE_VACATION_SCOPES,
    load_google_credentials,
)
from .utils import format_http_error, resolve_required_path

PHONE_PATTERN = re.compile(r"Telefon ucznia:\s*(.+)")


@dataclass(frozen=True)
class CalendarLessonEvent:
    student_name: str
    lesson_date: date
    start_time: datetime | None = None
    end_time: datetime | None = None
    student_email: str | None = None
    student_phone: str | None = None


class LessonCalendarProvider(Protocol):
    def list_lessons_in_range(
        self,
        *,
        start_date: date,
        end_date: date,
    ) -> list[CalendarLessonEvent]: ...


class GoogleCalendarLessonProvider:
    def __init__(
        self,
        *,
        credentials_path: str | Path | None = "credentials.json",
        token_path: str | Path | None = "token.json",
        calendar_id: str = "primary",
        include_drive_scope: bool = False,
    ) -> None:
        self._credentials_path = resolve_required_path(
            explicit_path=credentials_path,
            env_var_name="GOOGLE_CREDENTIALS_PATH"
        )
        self._token_path = resolve_required_path(
            explicit_path=token_path,
            env_var_name="GOOGLE_TOKEN_PATH"
        )
        self._calendar_id = calendar_id
        self._include_drive_scope = include_drive_scope

    def list_lessons_in_range(
        self,
        *,
        start_date: date,
        end_date: date,
    ) -> list[CalendarLessonEvent]:
        calendar_service = self._build_calendar_service()
        start_dt = datetime.combine(start_date, time.min).isoformat() + "Z"
        end_exclusive = datetime.combine(end_date + timedelta(days=1), time.min)
        end_dt = end_exclusive.isoformat() + "Z"

        page_token: str | None = None
        events: list[CalendarLessonEvent] = []

        try:
            while True:
                response = (
                    calendar_service.events()
                    .list(
                        calendarId=self._calendar_id,
                        timeMin=start_dt,
                        timeMax=end_dt,
                        singleEvents=True,
                        orderBy="startTime",
                        fields="nextPageToken, items(summary, description, start, end, attendees)",
                        pageToken=page_token,
                    )
                    .execute()
                )

                for item in response.get("items", []):
                    summary = item.get("summary")
                    start_value = _extract_lesson_start(item.get("start"))
                    end_value = _extract_lesson_datetime(item.get("end"))
                    lesson_date = _extract_lesson_date(item.get("start"), start_value)
                    if (
                        not isinstance(summary, str)
                        or not summary.strip()
                        or lesson_date is None
                    ):
                        continue

                    student_email = _extract_student_email(item.get("attendees"))
                    student_phone = _extract_student_phone(item.get("description"))
                    events.append(
                        CalendarLessonEvent(
                            student_name=summary.strip(),
                            lesson_date=lesson_date,
                            start_time=start_value,
                            end_time=end_value,
                            student_email=student_email,
                            student_phone=student_phone,
                        )
                    )

                page_token = response.get("nextPageToken")
                if not page_token:
                    break
        except HttpError as exc:
            raise RuntimeError(
                "Error downloading events from Google Calendar. "
                f"Details: {format_http_error(exc)}"
            ) from exc

        return events

    def _build_calendar_service(self):
        scopes = (
            GOOGLE_CALENDAR_DRIVE_SCOPES
            if self._include_drive_scope
            else GOOGLE_VACATION_SCOPES
        )
        credentials = load_google_credentials(
            credentials_path=self._credentials_path,
            token_path=self._token_path,
            scopes=scopes,
        )
        return build("calendar", "v3", credentials=credentials)


def _extract_lesson_start(raw_start: object) -> datetime | None:
    return _extract_lesson_datetime(raw_start)


def _extract_lesson_datetime(raw_value: object) -> datetime | None:
    if not isinstance(raw_value, dict):
        return None

    date_time_value = raw_value.get("dateTime")
    if isinstance(date_time_value, str):
        normalized = date_time_value.replace("Z", "+00:00")
        return datetime.fromisoformat(normalized)

    return None


def _extract_lesson_date(raw_start: object, start: datetime | None) -> date | None:
    if start is not None:
        return start.date()

    if not isinstance(raw_start, dict):
        return None

    date_value = raw_start.get("date")
    if isinstance(date_value, str):
        return date.fromisoformat(date_value)

    return None


def _extract_student_email(raw_attendees: object) -> str | None:
    if not isinstance(raw_attendees, list):
        return None

    for attendee in raw_attendees:
        if not isinstance(attendee, dict):
            continue
        email = attendee.get("email")
        if not isinstance(email, str) or not email.strip():
            continue
        if attendee.get("self"):
            continue
        return email.strip()

    return None


def _extract_student_phone(description: object) -> str | None:
    if not isinstance(description, str):
        return None

    match = PHONE_PATTERN.search(description)
    if not match:
        return None

    phone = match.group(1).strip()
    return phone or None

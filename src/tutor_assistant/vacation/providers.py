"""Providers and integrations for vacation notifications flow."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from email.message import EmailMessage
from pathlib import Path
import base64
import os
import re
from typing import Protocol

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from tutor_assistant.core import GOOGLE_VACATION_SCOPES, load_google_credentials

from .models import CalendarLessonEvent

PHONE_PATTERN = re.compile(r"Telefon ucznia:\s*(.+)")


class LessonCalendarProvider(Protocol):
    def list_lessons_in_range(
        self,
        *,
        start_date: date,
        end_date: date,
    ) -> list[CalendarLessonEvent]: ...


class StudentEmailProvider(Protocol):
    def send_vacation_notice(
        self,
        *,
        recipient_email: str,
        subject: str,
        body: str,
    ) -> None: ...


class InMemoryLessonCalendarProvider:
    def __init__(self, events: list[CalendarLessonEvent] | None = None) -> None:
        self._events = events or []

    def list_lessons_in_range(
        self,
        *,
        start_date: date,
        end_date: date,
    ) -> list[CalendarLessonEvent]:
        return [
            event
            for event in self._events
            if start_date <= event.lesson_date <= end_date
        ]


class InMemoryEmailProvider:
    def __init__(self) -> None:
        self.sent_messages: list[tuple[str, str, str]] = []

    def send_vacation_notice(
        self,
        *,
        recipient_email: str,
        subject: str,
        body: str,
    ) -> None:
        self.sent_messages.append((recipient_email, subject, body))


class GoogleCalendarLessonProvider:
    def __init__(
        self,
        *,
        credentials_path: str | Path | None = None,
        token_path: str | Path | None = None,
        calendar_id: str = "primary",
    ) -> None:
        self._credentials_path = Path(
            credentials_path or os.getenv("GOOGLE_CREDENTIALS_PATH", "credentials.json")
        )
        self._token_path = Path(
            token_path or os.getenv("GOOGLE_TOKEN_PATH", "token.json")
        )
        self._calendar_id = calendar_id

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
                        fields="nextPageToken, items(summary, description, start, attendees)",
                        pageToken=page_token,
                    )
                    .execute()
                )

                for item in response.get("items", []):
                    summary = item.get("summary")
                    lesson_date = _extract_lesson_date(item.get("start"))
                    if (
                        not isinstance(summary, str)
                        or not summary.strip()
                        or not lesson_date
                    ):
                        continue

                    student_email = _extract_student_email(item.get("attendees"))
                    student_phone = _extract_student_phone(item.get("description"))
                    events.append(
                        CalendarLessonEvent(
                            student_name=summary.strip(),
                            lesson_date=lesson_date,
                            student_email=student_email,
                            student_phone=student_phone,
                        )
                    )

                page_token = response.get("nextPageToken")
                if not page_token:
                    break
        except HttpError as exc:
            raise RuntimeError(
                "Nie udalo sie pobrac wydarzen z Google Calendar. "
                f"Szczegoly: {_format_http_error(exc)}"
            ) from exc

        return events

    def _build_calendar_service(self):
        credentials = load_google_credentials(
            credentials_path=self._credentials_path,
            token_path=self._token_path,
            scopes=GOOGLE_VACATION_SCOPES,
        )
        return build("calendar", "v3", credentials=credentials)


class GmailProvider:
    def __init__(
        self,
        *,
        credentials_path: str | Path | None = None,
        token_path: str | Path | None = None,
        sender_email: str | None = None,
    ) -> None:
        self._credentials_path = Path(
            credentials_path or os.getenv("GOOGLE_CREDENTIALS_PATH", "credentials.json")
        )
        self._token_path = Path(
            token_path or os.getenv("GOOGLE_TOKEN_PATH", "token.json")
        )
        self._sender_email = sender_email or os.getenv("GMAIL_SENDER_EMAIL", "me")

    def send_vacation_notice(
        self,
        *,
        recipient_email: str,
        subject: str,
        body: str,
    ) -> None:
        gmail_service = self._build_gmail_service()

        message = EmailMessage()
        message["To"] = recipient_email
        message["From"] = self._sender_email
        message["Subject"] = subject
        message.set_content(body)

        encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")
        payload = {"raw": encoded_message}

        try:
            gmail_service.users().messages().send(userId="me", body=payload).execute()
        except HttpError as exc:
            raise RuntimeError(
                f"Nie udalo sie wyslac e-maila do {recipient_email}. "
                f"Szczegoly: {_format_http_error(exc)}"
            ) from exc

    def _build_gmail_service(self):
        credentials = load_google_credentials(
            credentials_path=self._credentials_path,
            token_path=self._token_path,
            scopes=GOOGLE_VACATION_SCOPES,
        )
        return build("gmail", "v1", credentials=credentials)


def _extract_lesson_date(raw_start: object) -> date | None:
    if not isinstance(raw_start, dict):
        return None

    date_time_value = raw_start.get("dateTime")
    if isinstance(date_time_value, str):
        normalized = date_time_value.replace("Z", "+00:00")
        return datetime.fromisoformat(normalized).date()

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
        if attendee.get("self") is True:
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


def _format_http_error(error: HttpError) -> str:
    status = getattr(error.resp, "status", "unknown")
    reason = getattr(error, "reason", None)
    if isinstance(reason, str) and reason:
        return f"HTTP {status}: {reason}"
    return f"HTTP {status}: {error}"

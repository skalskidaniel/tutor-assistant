from __future__ import annotations

from datetime import datetime, timedelta
import os
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest

from tutor import GmailProvider  # pyright: ignore[reportMissingImports]
from tutor import GoogleCalendarLessonProvider  # pyright: ignore[reportMissingImports]
from tutor import GoogleMeetProvider  # pyright: ignore[reportMissingImports]
from tutor import MeetingSchedule  # pyright: ignore[reportMissingImports]
from tutor import Student  # pyright: ignore[reportMissingImports]
from tutor import VacationNotificationService  # pyright: ignore[reportMissingImports]
from tutor import VacationRequest  # pyright: ignore[reportMissingImports]


@pytest.mark.integration
def test_vacation_calendar_provider_integration_real_api() -> None:
    run_enabled = (
        os.getenv("GOOGLE_ENABLE_ALL_INTEGRATION_TESTS") == "1"
        or os.getenv("GOOGLE_ENABLE_VACATION_INTEGRATION_TEST") == "1"
    )
    if not run_enabled:
        pytest.skip(
            "Test vacation-calendar jest opt-in. Ustaw GOOGLE_ENABLE_VACATION_INTEGRATION_TEST=1 "
            "lub GOOGLE_ENABLE_ALL_INTEGRATION_TESTS=1."
        )

    credentials_path = os.getenv("GOOGLE_CREDENTIALS_PATH", "credentials.json")
    if not os.path.exists(credentials_path):
        pytest.skip("Brak credentials.json dla testu integracyjnego Google API.")

    start = datetime.now(ZoneInfo("Europe/Warsaw")) + timedelta(days=2)
    request = Student(
        first_name="IntegracjaUrlop",
        last_name=f"Testowa{uuid4().hex[:6]}",
        email=os.getenv("GOOGLE_TEST_STUDENT_EMAIL", "integracja.test@example.com"),
        phone="+48500100200",
    )
    meet_provider = GoogleMeetProvider(
        schedule=MeetingSchedule(
            meeting_date=start.date(),
            hour=start.hour,
            minute=start.minute,
            recurrence="none",
        )
    )

    try:
        meet_provider.create_personal_meeting(request)

        calendar_provider = GoogleCalendarLessonProvider()
        service = VacationNotificationService(
            calendar_provider=calendar_provider,
            schedule_url="https://example.com/schedule",
        )
        result = service.prepare_notifications(
            request=VacationRequest(start_date=start.date(), end_date=start.date()),
            send_emails=False,
        )
    finally:
        meet_provider.delete_last_created_meeting()

    matching_notices = [
        notice for notice in result.notices if notice.student_name == request.full_name
    ]
    assert matching_notices, "Nie znaleziono wydarzenia ucznia w zakresie urlopu."

    notice = matching_notices[0]
    assert notice.student_phone == request.phone
    assert start.date() in notice.lesson_dates
    assert start.strftime("%d.%m.%Y") in notice.message


@pytest.mark.integration
def test_vacation_gmail_provider_integration_real_api() -> None:
    credentials_path = os.getenv("GOOGLE_CREDENTIALS_PATH", "credentials.json")
    recipient = os.getenv("GOOGLE_TEST_STUDENT_EMAIL")
    run_enabled = (
        os.getenv("GOOGLE_ENABLE_ALL_INTEGRATION_TESTS") == "1"
        or os.getenv("GOOGLE_ENABLE_GMAIL_INTEGRATION_TEST") == "1"
    )

    if not os.path.exists(credentials_path):
        pytest.skip("Brak credentials.json dla testu integracyjnego Gmail API.")
    if not recipient:
        pytest.skip("Brak GOOGLE_TEST_STUDENT_EMAIL dla testu Gmail API.")
    if not run_enabled:
        pytest.skip(
            "Test wysylki Gmail jest opt-in. Ustaw GOOGLE_ENABLE_GMAIL_INTEGRATION_TEST=1 "
            "lub GOOGLE_ENABLE_ALL_INTEGRATION_TESTS=1."
        )

    provider = GmailProvider()
    provider.send_vacation_notice(
        recipient_email=recipient,
        subject=f"[TEST] Zmiana terminu zajec {uuid4().hex[:8]}",
        body=(
            "Czesc, to test integracyjny Gmail API dla use case 3. "
            "Wiadomosc mozna zignorowac."
        ),
    )

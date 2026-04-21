import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from tutor_assistant import GoogleDriveProvider  # pyright: ignore[reportMissingImports]
from tutor_assistant import GoogleMeetProvider  # pyright: ignore[reportMissingImports]
from tutor_assistant import MeetingSchedule  # pyright: ignore[reportMissingImports]
from tutor_assistant import NewStudentRequest  # pyright: ignore[reportMissingImports]
from tutor_assistant import StudentWelcomeService  # pyright: ignore[reportMissingImports]
from tutor_assistant import WelcomePackage  # pyright: ignore[reportMissingImports]


@pytest.mark.integration
def test_google_providers_integration_real_api() -> None:
    run_enabled = (
        os.getenv("GOOGLE_ENABLE_ALL_INTEGRATION_TESTS") == "1"
        or os.getenv("GOOGLE_ENABLE_ONBOARDING_INTEGRATION_TEST") == "1"
    )
    if not run_enabled:
        pytest.skip(
            "Test wysylki Gmail jest opt-in. Ustaw GOOGLE_ENABLE_ONBOARDING_INTEGRATION_TEST=1 "
            "lub GOOGLE_ENABLE_ALL_INTEGRATION_TESTS=1."
        )

    credentials_path = os.getenv("GOOGLE_CREDENTIALS_PATH", "credentials.json")
    if not os.path.exists(credentials_path):
        pytest.skip("Brak credentials.json dla testu integracyjnego Google API.")

    start = datetime.now(ZoneInfo("Europe/Warsaw")) + timedelta(days=1)
    request = NewStudentRequest(
        first_name="Integracja",
        last_name="Testowa",
        email=os.getenv("GOOGLE_TEST_STUDENT_EMAIL", "integracja.test@example.com"),
        phone="+48500100200",
    )
    schedule = MeetingSchedule(
        meeting_date=start.date(),
        hour=start.hour,
        minute=start.minute,
        recurrence="weekly",
        occurrences=2,
    )
    meet_provider = GoogleMeetProvider()
    drive_provider = GoogleDriveProvider()
    service = StudentWelcomeService(
        meet_provider=meet_provider,
        drive_provider=drive_provider,
    )

    try:
        result = service.onboard_student(request, schedule)
    finally:
        meet_provider.delete_last_created_meeting()
        drive_provider.delete_last_created_workspace()

    assert isinstance(result, WelcomePackage)
    assert result.meet_link.startswith("https://meet.google.com/")
    assert result.drive_folder_url.startswith("https://drive.google.com/")
    assert result.meet_link in result.message_for_student
    assert result.drive_folder_url in result.message_for_student
    assert request.phone in result.message_for_student

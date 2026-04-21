from tutor import Student  # pyright: ignore[reportMissingImports]
from tutor import StudentWelcomeService  # pyright: ignore[reportMissingImports]
from tutor import WelcomePackage  # pyright: ignore[reportMissingImports]
from tests.mocks import InMemoryMeetProvider
from tutor.onboarding import (  # pyright: ignore[reportMissingImports]
    MeetingSchedule,
    slugify,
)


class FakeDriveProvider:
    def create_student_workspace(self, student: Student) -> str:
        return f"https://drive.google.com/drive/folders/{student.folder_slug}-fake"


def test_slugify_polish_characters_and_separators() -> None:
    assert slugify("Żaneta Łęcka") == "zaneta-lecka"
    assert slugify("  Ala---ma_kota!! ") == "ala-ma-kota"


def test_onboard_student_returns_welcome_package() -> None:
    service = StudentWelcomeService(
        meet_provider=InMemoryMeetProvider(),
        drive_provider=FakeDriveProvider(),
    )
    request = Student(
        first_name="Jan",
        last_name="Kowalski",
        email="jan.kowalski@example.com",
        phone="+48500100200",
    )
    from datetime import date
    schedule = MeetingSchedule(
        meeting_date=date(2026, 4, 18),
        hour=18,
        minute=0,
        recurrence="weekly",
    )

    result = service.onboard_student(request, schedule)

    assert isinstance(result, WelcomePackage)
    assert result.meet_link.startswith("https://meet.google.com/jan-kowalski-")
    assert result.drive_folder_url.startswith(
        "https://drive.google.com/drive/folders/jan-kowalski-"
    )
    assert "Google Meet" in result.message_for_student
    assert result.drive_folder_url in result.message_for_student
    assert request.first_name in result.message_for_student

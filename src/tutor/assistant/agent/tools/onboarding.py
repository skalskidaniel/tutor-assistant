from typing import Callable, Literal

from tutor.onboarding import (
    MeetingSchedule,
    Student,
    StudentWelcomeService,
)
from .common import agent_tool, parse_date_value, tool_error_message


def make_onboard_student_tool(service: StudentWelcomeService) -> Callable[..., object]:
    @agent_tool
    def onboard_student(
        first_name: str,
        last_name: str,
        email: str,
        phone: str,
        meeting_date: str,
        hour: int,
        minute: int,
        recurrence: Literal["none", "weekly", "biweekly"] = "weekly",
        occurrences: int | None = None,
    ) -> str:
        """Onboarduje nowego ucznia i tworzy link Meet oraz folder na Google Drive."""
        try:
            request = Student(
                first_name=first_name,
                last_name=last_name,
                email=email,
                phone=phone,
            )
            schedule = MeetingSchedule(
                meeting_date=parse_date_value(meeting_date, field_name="meeting_date"),
                hour=hour,
                minute=minute,
                recurrence=recurrence,
                occurrences=occurrences,
            )

            package = service.onboard_student(request, schedule)

            return (
                "Onboarding zakończony pomyślnie.\n"
                f"Google Meet: {package.meet_link}\n"
                f"Google Drive: {package.drive_folder_url}\n"
                "Wiadomość do ucznia:\n"
                f"{package.message_for_student}"
            )
        except Exception as exc:  # noqa: BLE001
            return tool_error_message(exc)

    return onboard_student

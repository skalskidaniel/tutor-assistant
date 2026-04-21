from __future__ import annotations

from datetime import date
from uuid import uuid4

from tutor.core import CalendarLessonEvent as LessonEvent
from tutor.onboarding import Student, MeetingSchedule


class InMemoryLessonCalendarProvider:
    """Used only inside integration tests"""

    def __init__(self, events: list[LessonEvent]) -> None:
        self.events = events

    def list_lessons_in_range(self, *, start_date: date, end_date: date) -> list[LessonEvent]:
        return [
            event
            for event in self.events
            if start_date <= event.lesson_date <= end_date
        ]


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


class InMemoryEmailProvider:
    """Used only inside integration tests"""

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

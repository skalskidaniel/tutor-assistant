from __future__ import annotations

import os
from collections import defaultdict
from datetime import date

from tutor.core.calendar import CalendarLessonEvent, LessonCalendarProvider

from .models import (
    StudentVacationNotice,
    VacationRequest,
    VacationResult,
)
from .providers import StudentEmailProvider


class VacationNotificationService:
    def __init__(
        self,
        *,
        calendar_provider: LessonCalendarProvider,
        email_provider: StudentEmailProvider | None = None,
        schedule_url: str | None = None,
    ) -> None:
        self._calendar_provider = calendar_provider
        self._email_provider = email_provider
        resolved_schedule_url = schedule_url or os.getenv("GOOGLE_BOOK_SCHEDULE_URL")
        if not resolved_schedule_url:
            raise ValueError(
                f"You must configure GOOGLE_BOOK_SCHEDULE_URL before initializing {type(self).__name__}"
            )
        self._schedule_url = resolved_schedule_url

    def prepare_notifications(
        self,
        *,
        request: VacationRequest,
        send_emails: bool,
    ) -> VacationResult:
        lesson_events = self._calendar_provider.list_lessons_in_range(
            start_date=request.start_date,
            end_date=request.end_date,
        )
        grouped = self._group_events_by_student(lesson_events)

        notices: list[StudentVacationNotice] = []
        for student_name in sorted(grouped):
            student_events = grouped[student_name]
            lesson_dates = _unique_sorted_dates(student_events)
            student_phone = _first_non_empty(
                [event.student_phone for event in student_events]
            )
            student_email = _first_non_empty(
                [event.student_email for event in student_events]
            )

            message = self._build_student_message(lesson_dates)
            email_sent = False

            if send_emails and student_email:
                if self._email_provider is None:
                    raise ValueError(
                        "email_provider have not been configured"
                    )
                self._email_provider.send_vacation_notice(
                    recipient_email=student_email,
                    subject="Zmiana terminu zajęć",
                    body=message,
                )
                email_sent = True

            notices.append(
                StudentVacationNotice(
                    student_name=student_name,
                    lesson_dates=lesson_dates,
                    message=message,
                    student_phone=student_phone,
                    student_email=student_email,
                    email_sent=email_sent,
                )
            )

        return VacationResult(notices=tuple(notices), scanned_events=len(lesson_events))

    @staticmethod
    def _group_events_by_student(
        events: list[CalendarLessonEvent],
    ) -> dict[str, list[CalendarLessonEvent]]:
        grouped: dict[str, list[CalendarLessonEvent]] = defaultdict(list)
        for event in events:
            grouped[event.student_name].append(event)
        return grouped

    def _build_student_message(self, lesson_dates: tuple[date, ...]) -> str:
        dates_text = ", ".join(_format_date(value) for value in lesson_dates)
        return (
            "Cześć, z powodu mojej nieobecności musimy przełożyć/odwołać nasze zajęcia "
            f"z dni{"a" if len(lesson_dates) == 1 else ""} {dates_text}. "
            "Możesz sprawdzić dostępne terminy w moim harmonogramie: "
            f"{self._schedule_url}"
        )


def _unique_sorted_dates(events: list[CalendarLessonEvent]) -> tuple[date, ...]:
    return tuple(sorted({event.lesson_date for event in events}))


def _first_non_empty(values: list[str | None]) -> str | None:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _format_date(value: date) -> str:
    return value.strftime("%d.%m.%Y")

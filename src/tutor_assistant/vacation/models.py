"""Domain models for vacation notifications use case."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class VacationRequest:
    start_date: date
    end_date: date

    def __post_init__(self) -> None:
        if self.end_date < self.start_date:
            raise ValueError("end_date nie moze byc wczesniejsza niz start_date.")


@dataclass(frozen=True)
class StudentVacationNotice:
    student_name: str
    lesson_dates: tuple[date, ...]
    message: str
    student_phone: str | None
    student_email: str | None
    email_sent: bool = False


@dataclass(frozen=True)
class VacationResult:
    notices: tuple[StudentVacationNotice, ...]
    scanned_events: int

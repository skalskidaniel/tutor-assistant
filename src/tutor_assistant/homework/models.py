"""Domain models for homework management use case."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime


@dataclass(frozen=True)
class HomeworkDatabaseFile:
    id: str
    name: str


@dataclass(frozen=True)
class CopiedHomeworkFile:
    id: str
    name: str


@dataclass(frozen=True)
class HomeworkAssignment:
    student_name: str
    lesson_date: date
    lesson_start_time: datetime | None
    lesson_end_time: datetime | None
    source_notes_pdf_name: str | None
    notes_summary: str | None
    selected_homework_name: str | None
    uploaded_homework_name: str | None
    status: str
    status_details: str


@dataclass(frozen=True)
class HomeworkUploadResult:
    assignments: tuple[HomeworkAssignment, ...]
    scanned_events: int
    uploaded_homeworks: int

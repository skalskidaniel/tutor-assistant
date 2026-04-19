"""Domain models for daily summary use case."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime


@dataclass(frozen=True)
class LessonInsights:
    recent_notes_summary: str


@dataclass(frozen=True)
class ExtractedRecentPages:
    recent_page_images_png: tuple[bytes, ...]
    page_count: int


@dataclass(frozen=True)
class LatestNotesPdf:
    file_name: str
    file_id: str
    pdf_bytes: bytes
    modified_time: datetime


@dataclass(frozen=True)
class DailyLessonSummary:
    student_name: str
    lesson_date: date
    lesson_start_time: datetime | None
    lesson_end_time: datetime | None
    source_pdf_name: str | None
    recent_notes_summary: str


@dataclass(frozen=True)
class DailySummaryResult:
    lesson_summaries: tuple[DailyLessonSummary, ...]
    scanned_events: int

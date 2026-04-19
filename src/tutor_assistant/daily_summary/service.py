"""Application service for daily summary flow."""

from __future__ import annotations

from datetime import date

from tutor_assistant.core.calendar import CalendarLessonEvent, LessonCalendarProvider

from .models import DailyLessonSummary, DailySummaryResult
from .providers import (
    LessonInsightsProvider,
    PdfRecentPagesProvider,
    StudentNotesProvider,
)


class DailySummaryService:
    def __init__(
        self,
        *,
        calendar_provider: LessonCalendarProvider,
        notes_provider: StudentNotesProvider,
        pdf_recent_pages_provider: PdfRecentPagesProvider,
        insights_provider: LessonInsightsProvider,
    ) -> None:
        self._calendar_provider = calendar_provider
        self._notes_provider = notes_provider
        self._pdf_recent_pages_provider = pdf_recent_pages_provider
        self._insights_provider = insights_provider

    def build_summary_for_day(self, *, target_date: date) -> DailySummaryResult:
        events = self._calendar_provider.list_lessons_in_range(
            start_date=target_date,
            end_date=target_date,
        )

        lesson_summaries: list[DailyLessonSummary] = []
        for event in sorted(events, key=_event_sort_key):
            latest_pdf = self._notes_provider.get_latest_notes_pdf(
                student_name=event.student_name
            )

            if latest_pdf is None:
                lesson_summaries.append(
                    DailyLessonSummary(
                        student_name=event.student_name,
                        lesson_date=event.lesson_date,
                        lesson_start_time=event.start_time,
                        lesson_end_time=event.end_time,
                        source_pdf_name=None,
                        recent_notes_summary="Brak notatek PDF w folderze notatki.",
                    )
                )
                continue

            extracted_pages = self._pdf_recent_pages_provider.extract_recent_pages(
                pdf_bytes=latest_pdf.pdf_bytes
            )
            insights = self._insights_provider.analyze_lesson_notes(
                extracted_pages=extracted_pages
            )

            lesson_summaries.append(
                DailyLessonSummary(
                    student_name=event.student_name,
                    lesson_date=event.lesson_date,
                    lesson_start_time=event.start_time,
                    lesson_end_time=event.end_time,
                    source_pdf_name=latest_pdf.file_name,
                    recent_notes_summary=insights.recent_notes_summary,
                )
            )

        return DailySummaryResult(
            lesson_summaries=tuple(lesson_summaries),
            scanned_events=len(events),
        )


def _event_sort_key(event: CalendarLessonEvent) -> tuple[int, str]:
    if event.start_time is not None:
        return (0, event.start_time.isoformat())
    return (1, event.lesson_date.isoformat())

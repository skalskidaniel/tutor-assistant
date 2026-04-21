"""Application service for daily summary flow."""

from __future__ import annotations

import asyncio
from datetime import date

from tutor_assistant.core.calendar import CalendarLessonEvent, LessonCalendarProvider

from .models import DailyLessonSummary, DailySummaryResult
from .providers import (
    LessonInsightsProvider,
    PdfRecentPagesProvider,
    StudentNotesProvider,
)


from typing import Callable


class DailySummaryService:
    def __init__(
        self,
        *,
        calendar_provider: LessonCalendarProvider,
        notes_provider: StudentNotesProvider,
        pdf_recent_pages_provider: PdfRecentPagesProvider,
        insights_provider: LessonInsightsProvider,
        max_concurrency: int = 4,
        progress_callback: Callable[[str], None] | None = None,
    ) -> None:
        if max_concurrency < 1:
            raise ValueError("max_concurrency musi byc wieksze od zera.")

        self._calendar_provider = calendar_provider
        self._notes_provider = notes_provider
        self._pdf_recent_pages_provider = pdf_recent_pages_provider
        self._insights_provider = insights_provider
        self._max_concurrency = max_concurrency
        self._progress_callback = progress_callback

    def build_summary_for_day(self, *, target_date: date) -> DailySummaryResult:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(
                self.build_summary_for_day_async(target_date=target_date)
            )

        raise RuntimeError(
            "build_summary_for_day nie moze byc wywolane wewnatrz aktywnej petli "
            "asyncio. Uzyj await build_summary_for_day_async(...)."
        )

    async def build_summary_for_day_async(
        self, *, target_date: date
    ) -> DailySummaryResult:
        events = await asyncio.to_thread(
            self._calendar_provider.list_lessons_in_range,
            start_date=target_date,
            end_date=target_date,
        )
        ordered_events = sorted(events, key=_event_sort_key)

        semaphore = asyncio.Semaphore(self._max_concurrency)

        async def _process_event(event: CalendarLessonEvent) -> DailyLessonSummary:
            async with semaphore:
                return await self._build_lesson_summary(event=event)

        lesson_summaries = await asyncio.gather(
            *(_process_event(event) for event in ordered_events)
        )

        return DailySummaryResult(
            lesson_summaries=tuple(lesson_summaries),
            scanned_events=len(events),
        )

    async def _build_lesson_summary(
        self, *, event: CalendarLessonEvent
    ) -> DailyLessonSummary:
        if self._progress_callback:
            self._progress_callback(
                f"[bold cyan]Szukam notatek dla ucznia:[/bold cyan] {event.student_name}..."
            )

        latest_pdf = await asyncio.to_thread(
            self._notes_provider.get_latest_notes_pdf,
            student_name=event.student_name,
        )

        if latest_pdf is None:
            return DailyLessonSummary(
                student_name=event.student_name,
                lesson_date=event.lesson_date,
                lesson_start_time=event.start_time,
                lesson_end_time=event.end_time,
                source_pdf_name=None,
                recent_notes_summary="Brak notatek PDF w folderze notatki.",
            )

        if self._progress_callback:
            self._progress_callback(
                f"[bold yellow]Analizowanie notatek w Bedrock (AI)...[/bold yellow] ({event.student_name})"
            )

        extracted_pages = await asyncio.to_thread(
            self._pdf_recent_pages_provider.extract_recent_pages,
            pdf_bytes=latest_pdf.pdf_bytes,
        )
        insights = await asyncio.to_thread(
            self._insights_provider.analyze_lesson_notes,
            extracted_pages=extracted_pages,
        )

        if self._progress_callback:
            self._progress_callback(
                f"[bold green]Zakonczono analize notatek:[/bold green] {event.student_name}"
            )

        return DailyLessonSummary(
            student_name=event.student_name,
            lesson_date=event.lesson_date,
            lesson_start_time=event.start_time,
            lesson_end_time=event.end_time,
            source_pdf_name=latest_pdf.file_name,
            recent_notes_summary=insights.recent_notes_summary,
        )


def _event_sort_key(event: CalendarLessonEvent) -> tuple[int, str]:
    if event.start_time is not None:
        return (0, event.start_time.isoformat())
    return (1, event.lesson_date.isoformat())

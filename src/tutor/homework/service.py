"""Application service for homework management flow."""

from __future__ import annotations

import asyncio
from datetime import date

from tutor.core import LessonCalendarProvider
from tutor.core.calendar import CalendarLessonEvent
from tutor.daily_summary.models import LatestNotesPdf
from tutor.daily_summary.providers import (
    LessonInsightsProvider,
    PdfRecentPagesProvider,
    StudentNotesProvider,
)

from .models import DriveFile, HomeworkAssignment, HomeworkUploadResult
from .providers import HomeworkDriveProvider, HomeworkMatcher


from typing import Callable


class HomeworkService:
    def __init__(
        self,
        *,
        calendar_provider: LessonCalendarProvider,
        notes_provider: StudentNotesProvider,
        pdf_recent_pages_provider: PdfRecentPagesProvider,
        insights_provider: LessonInsightsProvider,
        homework_drive_provider: HomeworkDriveProvider,
        homework_matcher: HomeworkMatcher,
        max_concurrency: int = 4,
        progress_callback: Callable[[str], None] | None = None,
    ) -> None:
        if max_concurrency < 1:
            raise ValueError("max_concurrency must be positive.")

        self._calendar_provider = calendar_provider
        self._notes_provider = notes_provider
        self._pdf_recent_pages_provider = pdf_recent_pages_provider
        self._insights_provider = insights_provider
        self._homework_drive_provider = homework_drive_provider
        self._homework_matcher = homework_matcher
        self._max_concurrency = max_concurrency
        self._progress_callback = progress_callback

    def upload_homework_for_day(self, *, target_date: date) -> HomeworkUploadResult:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(
                self.upload_homework_for_day_async(target_date=target_date)
            )

        raise RuntimeError(
            "upload_homework_for_day cannot be called inside an active asyncio loop. "
            "Use await upload_homework_for_day_async(...)."
        )

    async def upload_homework_for_day_async(
        self, *, target_date: date
    ) -> HomeworkUploadResult:
        events = await asyncio.to_thread(
            self._calendar_provider.list_lessons_in_range,
            start_date=target_date,
            end_date=target_date,
        )
        ordered_events = sorted(events, key=_event_sort_key)
        homework_files = await asyncio.to_thread(
            self._homework_drive_provider.list_homework_database_files
        )
        homework_by_name = {item.name: item for item in homework_files}
        available_names = tuple(homework_by_name)

        semaphore = asyncio.Semaphore(self._max_concurrency)

        async def _process_event(event: CalendarLessonEvent) -> HomeworkAssignment:
            async with semaphore:
                return await self._build_assignment(
                    event=event,
                    homework_by_name=homework_by_name,
                    available_names=available_names,
                )

        assignments = await asyncio.gather(
            *(_process_event(event) for event in ordered_events)
        )
        uploaded_homeworks = sum(
            1 for assignment in assignments if assignment.status == "uploaded"
        )
        return HomeworkUploadResult(
            assignments=tuple(assignments),
            scanned_events=len(events),
            uploaded_homeworks=uploaded_homeworks,
        )

    async def _build_assignment(
        self,
        *,
        event: CalendarLessonEvent,
        homework_by_name: dict[str, DriveFile],
        available_names: tuple[str, ...],
    ) -> HomeworkAssignment:
        if self._progress_callback:
            self._progress_callback(
                f"[bold cyan]Szukam notatek...[/bold cyan] ({event.student_name})"
            )

        latest_pdf = await asyncio.to_thread(
            self._notes_provider.get_latest_notes_pdf,
            student_name=event.student_name,
        )
        if latest_pdf is None:
            return _build_assignment_without_notes(event=event)

        if not available_names:
            return _build_assignment_empty_database(event=event, latest_pdf=latest_pdf)

        if self._progress_callback:
            self._progress_callback(
                f"[bold yellow]Analizowanie w Bedrock...[/bold yellow] ({event.student_name})"
            )

        extracted_pages = await asyncio.to_thread(
            self._pdf_recent_pages_provider.extract_recent_pages,
            pdf_bytes=latest_pdf.pdf_bytes,
        )
        insights = await asyncio.to_thread(
            self._insights_provider.analyze_lesson_notes,
            extracted_pages=extracted_pages,
        )
        notes_summary = insights.recent_notes_summary

        if self._progress_callback:
            self._progress_callback(
                f"[bold blue]Dopasowywanie zadan...[/bold blue] ({event.student_name})"
            )

        try:
            selected_name = await asyncio.to_thread(
                self._homework_matcher.select_homework_name,
                notes_summary=notes_summary,
                available_homework_names=available_names,
            )
        except RuntimeError as error:
            return _build_assignment_matcher_error(
                event=event,
                latest_pdf=latest_pdf,
                notes_summary=notes_summary,
                error=error,
            )

        if selected_name is None:
            return _build_assignment_no_match(
                event=event,
                latest_pdf=latest_pdf,
                notes_summary=notes_summary,
            )

        selected_file = homework_by_name.get(selected_name)
        if selected_file is None:
            return _build_assignment_unavailable_file(
                event=event,
                latest_pdf=latest_pdf,
                notes_summary=notes_summary,
                selected_name=selected_name,
            )

        student_homework_folder = await asyncio.to_thread(
            self._homework_drive_provider.find_student_homework_folder,
            student_name=event.student_name,
        )
        if student_homework_folder is None:
            return _build_assignment_missing_homework_folder(
                event=event,
                latest_pdf=latest_pdf,
                notes_summary=notes_summary,
                selected_file_name=selected_file.name,
            )

        if self._progress_callback:
            self._progress_callback(
                f"[bold green]Kopiowanie na Drive...[/bold green] ({event.student_name})"
            )

        try:
            copied = await asyncio.to_thread(
                self._homework_drive_provider.copy_homework_to_student,
                source_file_id=selected_file.id,
                source_file_name=selected_file.name,
                target_homework_folder_id=student_homework_folder,
            )
        except RuntimeError as error:
            return _build_assignment_upload_error(
                event=event,
                latest_pdf=latest_pdf,
                notes_summary=notes_summary,
                selected_file_name=selected_file.name,
                error=error,
            )

        if self._progress_callback:
            self._progress_callback(
                f"[bold green]Zakonczono:[/bold green] {event.student_name}"
            )

        return HomeworkAssignment(
            student_name=event.student_name,
            lesson_date=event.lesson_date,
            lesson_start_time=event.start_time,
            lesson_end_time=event.end_time,
            source_notes_pdf_name=latest_pdf.file_name,
            notes_summary=notes_summary,
            selected_homework_name=selected_file.name,
            uploaded_homework_name=copied.name,
            status="uploaded",
            status_details="Zadanie domowe zostalo skopiowane do folderu ucznia.",
        )


def _build_assignment_without_notes(
    *, event: CalendarLessonEvent
) -> HomeworkAssignment:
    return HomeworkAssignment(
        student_name=event.student_name,
        lesson_date=event.lesson_date,
        lesson_start_time=event.start_time,
        lesson_end_time=event.end_time,
        source_notes_pdf_name=None,
        notes_summary=None,
        selected_homework_name=None,
        uploaded_homework_name=None,
        status="missing_notes",
        status_details="Brak notatek PDF w folderze notatki.",
    )


def _build_assignment_empty_database(
    *,
    event: CalendarLessonEvent,
    latest_pdf: LatestNotesPdf,
) -> HomeworkAssignment:
    return HomeworkAssignment(
        student_name=event.student_name,
        lesson_date=event.lesson_date,
        lesson_start_time=event.start_time,
        lesson_end_time=event.end_time,
        source_notes_pdf_name=latest_pdf.file_name,
        notes_summary=None,
        selected_homework_name=None,
        uploaded_homework_name=None,
        status="empty_homework_database",
        status_details="Baza zadan domowych jest pusta.",
    )


def _build_assignment_matcher_error(
    *,
    event: CalendarLessonEvent,
    latest_pdf: LatestNotesPdf,
    notes_summary: str,
    error: RuntimeError,
) -> HomeworkAssignment:
    return HomeworkAssignment(
        student_name=event.student_name,
        lesson_date=event.lesson_date,
        lesson_start_time=event.start_time,
        lesson_end_time=event.end_time,
        source_notes_pdf_name=latest_pdf.file_name,
        notes_summary=notes_summary,
        selected_homework_name=None,
        uploaded_homework_name=None,
        status="matcher_error",
        status_details=str(error),
    )


def _build_assignment_no_match(
    *,
    event: CalendarLessonEvent,
    latest_pdf: LatestNotesPdf,
    notes_summary: str,
) -> HomeworkAssignment:
    return HomeworkAssignment(
        student_name=event.student_name,
        lesson_date=event.lesson_date,
        lesson_start_time=event.start_time,
        lesson_end_time=event.end_time,
        source_notes_pdf_name=latest_pdf.file_name,
        notes_summary=notes_summary,
        selected_homework_name=None,
        uploaded_homework_name=None,
        status="no_match",
        status_details=(
            "Nie znaleziono pasujacego zadania domowego w bazie na podstawie notatek."
        ),
    )


def _build_assignment_unavailable_file(
    *,
    event: CalendarLessonEvent,
    latest_pdf: LatestNotesPdf,
    notes_summary: str,
    selected_name: str,
) -> HomeworkAssignment:
    return HomeworkAssignment(
        student_name=event.student_name,
        lesson_date=event.lesson_date,
        lesson_start_time=event.start_time,
        lesson_end_time=event.end_time,
        source_notes_pdf_name=latest_pdf.file_name,
        notes_summary=notes_summary,
        selected_homework_name=selected_name,
        uploaded_homework_name=None,
        status="unavailable_file",
        status_details="Wybrane zadanie nie istnieje juz w bazie.",
    )


def _build_assignment_missing_homework_folder(
    *,
    event: CalendarLessonEvent,
    latest_pdf: LatestNotesPdf,
    notes_summary: str,
    selected_file_name: str,
) -> HomeworkAssignment:
    return HomeworkAssignment(
        student_name=event.student_name,
        lesson_date=event.lesson_date,
        lesson_start_time=event.start_time,
        lesson_end_time=event.end_time,
        source_notes_pdf_name=latest_pdf.file_name,
        notes_summary=notes_summary,
        selected_homework_name=selected_file_name,
        uploaded_homework_name=None,
        status="missing_student_homework_folder",
        status_details="Nie znaleziono folderu ucznia z katalogiem zadania-domowe.",
    )


def _build_assignment_upload_error(
    *,
    event: CalendarLessonEvent,
    latest_pdf: LatestNotesPdf,
    notes_summary: str,
    selected_file_name: str,
    error: RuntimeError,
) -> HomeworkAssignment:
    return HomeworkAssignment(
        student_name=event.student_name,
        lesson_date=event.lesson_date,
        lesson_start_time=event.start_time,
        lesson_end_time=event.end_time,
        source_notes_pdf_name=latest_pdf.file_name,
        notes_summary=notes_summary,
        selected_homework_name=selected_file_name,
        uploaded_homework_name=None,
        status="upload_error",
        status_details=str(error),
    )


def _event_sort_key(event: CalendarLessonEvent) -> tuple[int, str]:
    if event.start_time is not None:
        return (0, event.start_time.isoformat())
    return (1, event.lesson_date.isoformat())

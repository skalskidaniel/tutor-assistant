from __future__ import annotations

from datetime import date, datetime, timezone

from tutor_assistant.core import (  # pyright: ignore[reportMissingImports]
    CalendarLessonEvent,
    InMemoryLessonCalendarProvider,
)
from tutor_assistant.daily_summary.models import (  # pyright: ignore[reportMissingImports]
    ExtractedRecentPages,
    LatestNotesPdf,
    LessonInsights,
)
from tutor_assistant.homework import (  # pyright: ignore[reportMissingImports]
    HomeworkDatabaseFile,
    HomeworkService,
)


class FakeNotesProvider:
    def __init__(self, by_student: dict[str, LatestNotesPdf | None]) -> None:
        self._by_student = by_student

    def get_latest_notes_pdf(self, *, student_name: str) -> LatestNotesPdf | None:
        return self._by_student.get(student_name)


class FakeRecentPagesProvider:
    def extract_recent_pages(self, *, pdf_bytes: bytes) -> ExtractedRecentPages:
        return ExtractedRecentPages(recent_page_images_png=(pdf_bytes,), page_count=3)


class FakeInsightsProvider:
    def analyze_lesson_notes(
        self, *, extracted_pages: ExtractedRecentPages
    ) -> LessonInsights:
        marker = extracted_pages.recent_page_images_png[0].decode("utf-8")
        return LessonInsights(recent_notes_summary=marker)


class FakeMatcher:
    def __init__(self, mapping: dict[str, str | None]) -> None:
        self._mapping = mapping

    def select_homework_name(
        self,
        *,
        notes_summary: str,
        available_homework_names: tuple[str, ...],  # noqa: ARG002
    ) -> str | None:
        return self._mapping.get(notes_summary)


class FakeHomeworkDriveProvider:
    def __init__(
        self,
        *,
        files: list[HomeworkDatabaseFile],
        student_homework_folders: dict[str, str | None],
        failing_source_ids: set[str] | None = None,
    ) -> None:
        self._files = files
        self._student_homework_folders = student_homework_folders
        self._failing_source_ids = failing_source_ids or set()
        self.copy_calls: list[tuple[str, str, str]] = []

    def list_homework_database_files(self) -> list[HomeworkDatabaseFile]:
        return list(self._files)

    def find_student_homework_folder(self, *, student_name: str) -> str | None:
        return self._student_homework_folders.get(student_name)

    def copy_homework_to_student(
        self,
        *,
        source_file_id: str,
        source_file_name: str,
        target_homework_folder_id: str,
    ):
        self.copy_calls.append(
            (source_file_id, source_file_name, target_homework_folder_id)
        )
        if source_file_id in self._failing_source_ids:
            raise RuntimeError("Drive copy failed")

        class _Copied:
            def __init__(self, name: str) -> None:
                self.name = name

        return _Copied(source_file_name)


class FailingMatcher:
    def select_homework_name(
        self,
        *,
        notes_summary: str,  # noqa: ARG002
        available_homework_names: tuple[str, ...],  # noqa: ARG002
    ) -> str | None:
        raise RuntimeError("Bedrock timeout")


def _notes_pdf(name: str, marker: str) -> LatestNotesPdf:
    return LatestNotesPdf(
        file_name=name,
        file_id=f"id-{name}",
        pdf_bytes=marker.encode("utf-8"),
        modified_time=datetime(2026, 4, 20, 10, 0, tzinfo=timezone.utc),
    )


def test_homework_service_uploads_and_returns_detailed_statuses() -> None:
    target_date = date(2026, 4, 20)
    calendar_provider = InMemoryLessonCalendarProvider(
        events=[
            CalendarLessonEvent(
                student_name="Ala A",
                lesson_date=target_date,
                start_time=datetime(2026, 4, 20, 10, 0, tzinfo=timezone.utc),
            ),
            CalendarLessonEvent(
                student_name="Bartek B",
                lesson_date=target_date,
                start_time=datetime(2026, 4, 20, 11, 0, tzinfo=timezone.utc),
            ),
            CalendarLessonEvent(
                student_name="Celina C",
                lesson_date=target_date,
                start_time=datetime(2026, 4, 20, 12, 0, tzinfo=timezone.utc),
            ),
            CalendarLessonEvent(
                student_name="Dawid D",
                lesson_date=target_date,
                start_time=datetime(2026, 4, 20, 13, 0, tzinfo=timezone.utc),
            ),
        ]
    )
    notes_provider = FakeNotesProvider(
        {
            "Ala A": _notes_pdf("notatki-ala.pdf", "summary-ala"),
            "Bartek B": None,
            "Celina C": _notes_pdf("notatki-celina.pdf", "summary-celina"),
            "Dawid D": _notes_pdf("notatki-dawid.pdf", "summary-dawid"),
        }
    )
    drive_provider = FakeHomeworkDriveProvider(
        files=[
            HomeworkDatabaseFile(id="hw-1", name="funkcja-kwadratowa.pdf"),
            HomeworkDatabaseFile(id="hw-2", name="geometria.pdf"),
        ],
        student_homework_folders={
            "Ala A": "folder-ala",
            "Celina C": "folder-celina",
            "Dawid D": None,
        },
    )
    matcher = FakeMatcher(
        {
            "summary-ala": "funkcja-kwadratowa.pdf",
            "summary-celina": None,
            "summary-dawid": "geometria.pdf",
        }
    )

    service = HomeworkService(
        calendar_provider=calendar_provider,
        notes_provider=notes_provider,
        pdf_recent_pages_provider=FakeRecentPagesProvider(),
        insights_provider=FakeInsightsProvider(),
        homework_drive_provider=drive_provider,
        homework_matcher=matcher,
    )
    result = service.upload_homework_for_day(target_date=target_date)

    assert result.scanned_events == 4
    assert result.uploaded_homeworks == 1
    assert [assignment.student_name for assignment in result.assignments] == [
        "Ala A",
        "Bartek B",
        "Celina C",
        "Dawid D",
    ]
    assert [assignment.status for assignment in result.assignments] == [
        "uploaded",
        "missing_notes",
        "no_match",
        "missing_student_homework_folder",
    ]
    assert drive_provider.copy_calls == [("hw-1", "funkcja-kwadratowa.pdf", "folder-ala")]


def test_homework_service_handles_empty_database() -> None:
    target_date = date(2026, 4, 20)
    calendar_provider = InMemoryLessonCalendarProvider(
        events=[
            CalendarLessonEvent(
                student_name="Ela E",
                lesson_date=target_date,
                start_time=datetime(2026, 4, 20, 9, 0, tzinfo=timezone.utc),
            )
        ]
    )
    notes_provider = FakeNotesProvider(
        {
            "Ela E": _notes_pdf("notatki-ela.pdf", "summary-ela"),
        }
    )
    drive_provider = FakeHomeworkDriveProvider(
        files=[],
        student_homework_folders={"Ela E": "folder-ela"},
    )

    service = HomeworkService(
        calendar_provider=calendar_provider,
        notes_provider=notes_provider,
        pdf_recent_pages_provider=FakeRecentPagesProvider(),
        insights_provider=FakeInsightsProvider(),
        homework_drive_provider=drive_provider,
        homework_matcher=FakeMatcher({}),
    )
    result = service.upload_homework_for_day(target_date=target_date)

    assert result.scanned_events == 1
    assert result.uploaded_homeworks == 0
    assert len(result.assignments) == 1
    assert result.assignments[0].status == "empty_homework_database"


def test_homework_service_handles_matcher_and_upload_errors() -> None:
    target_date = date(2026, 4, 20)
    upload_error_drive = FakeHomeworkDriveProvider(
        files=[HomeworkDatabaseFile(id="hw-g", name="graniastoslupy.pdf")],
        student_homework_folders={"Gosia G": "folder-gosia"},
        failing_source_ids={"hw-g"},
    )
    upload_service = HomeworkService(
        calendar_provider=InMemoryLessonCalendarProvider(
            events=[
                CalendarLessonEvent(
                    student_name="Gosia G",
                    lesson_date=target_date,
                    start_time=datetime(2026, 4, 20, 15, 0, tzinfo=timezone.utc),
                )
            ]
        ),
        notes_provider=FakeNotesProvider(
            {
                "Gosia G": _notes_pdf("notatki-gosia.pdf", "summary-gosia"),
            }
        ),
        pdf_recent_pages_provider=FakeRecentPagesProvider(),
        insights_provider=FakeInsightsProvider(),
        homework_drive_provider=upload_error_drive,
        homework_matcher=FakeMatcher({"summary-gosia": "graniastoslupy.pdf"}),
    )
    upload_result = upload_service.upload_homework_for_day(target_date=target_date)
    assert upload_result.assignments[0].status == "upload_error"

    matcher_error_service = HomeworkService(
        calendar_provider=InMemoryLessonCalendarProvider(
            events=[
                CalendarLessonEvent(
                    student_name="Filip F",
                    lesson_date=target_date,
                    start_time=datetime(2026, 4, 20, 14, 0, tzinfo=timezone.utc),
                )
            ]
        ),
        notes_provider=FakeNotesProvider(
            {
                "Filip F": _notes_pdf("notatki-filip.pdf", "summary-filip"),
            }
        ),
        pdf_recent_pages_provider=FakeRecentPagesProvider(),
        insights_provider=FakeInsightsProvider(),
        homework_drive_provider=FakeHomeworkDriveProvider(
            files=[HomeworkDatabaseFile(id="hw-f", name="funkcje.pdf")],
            student_homework_folders={"Filip F": "folder-filip"},
        ),
        homework_matcher=FailingMatcher(),
    )
    matcher_result = matcher_error_service.upload_homework_for_day(target_date=target_date)
    assert matcher_result.assignments[0].status == "matcher_error"

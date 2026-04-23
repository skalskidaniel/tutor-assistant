from __future__ import annotations

from datetime import date, datetime, timezone

import pymupdf

from tutor.core import CalendarLessonEvent as LessonEvent
from tests.mocks import InMemoryLessonCalendarProvider
from tutor.daily_summary.models import (  # pyright: ignore[reportMissingImports]
    ExtractedRecentPages,
    LatestNotesPdf,
    LessonInsights,
)
from tutor.daily_summary.providers import (  # pyright: ignore[reportMissingImports]
    GoogleDriveStudentNotesProvider,
    PyMuPdfRecentPagesProvider,
    _parse_insights_json,
)
from tutor.daily_summary.service import (  # pyright: ignore[reportMissingImports]
    DailySummaryService,
)


class FakeStudentNotesProvider:
    def __init__(self, by_student: dict[str, LatestNotesPdf | None]) -> None:
        self._by_student = by_student

    def get_latest_notes_pdf(self, *, student_name: str) -> LatestNotesPdf | None:
        return self._by_student.get(student_name)


class FakeRecentPagesProvider:
    def extract_recent_pages(self, *, pdf_bytes: bytes) -> ExtractedRecentPages:
        return ExtractedRecentPages(
            recent_page_images_png=(pdf_bytes,),
            page_count=5,
        )


class FakeInsightsProvider:
    def analyze_lesson_notes(
        self, *, extracted_pages: ExtractedRecentPages
    ) -> LessonInsights:
        return LessonInsights(
            recent_notes_summary=f"Podsumowanie stron: {len(extracted_pages.recent_page_images_png)}"
        )


def test_daily_summary_service_uses_recent_pages_and_handles_missing_pdf() -> None:
    target_date = date(2026, 4, 17)
    calendar_provider = InMemoryLessonCalendarProvider(
            events=[
                LessonEvent(
                student_name="Jan Kowalski",
                lesson_date=target_date,
                start_time=datetime(2026, 4, 17, 15, 0, tzinfo=timezone.utc),
            ),
                LessonEvent(
                student_name="Anna Nowak",
                lesson_date=target_date,
                start_time=datetime(2026, 4, 17, 13, 0, tzinfo=timezone.utc),
            ),
        ]
    )
    notes_provider = FakeStudentNotesProvider(
        {
            "Anna Nowak": LatestNotesPdf(
                file_name="wielomiany.pdf",
                file_id="pdf-1",
                pdf_bytes=b"fake-image-bytes",
                modified_time=datetime(2026, 4, 16, 10, 0, tzinfo=timezone.utc),
            ),
            "Jan Kowalski": None,
        }
    )

    service = DailySummaryService(
        calendar_provider=calendar_provider,
        notes_provider=notes_provider,
        pdf_recent_pages_provider=FakeRecentPagesProvider(),
        insights_provider=FakeInsightsProvider(),
    )

    result = service.build_summary_for_day(target_date=target_date)

    assert result.scanned_events == 2
    assert len(result.lesson_summaries) == 2
    first, second = result.lesson_summaries

    assert first.student_name == "Anna Nowak"
    assert first.source_pdf_name == "wielomiany.pdf"
    assert first.recent_notes_summary == "Podsumowanie stron: 1"

    assert second.student_name == "Jan Kowalski"
    assert second.source_pdf_name is None
    assert "Brak notatek PDF" in second.recent_notes_summary


def test_pymupdf_recent_pages_provider_returns_last_three_page_images() -> None:
    document = pymupdf.open()
    for index in range(5):
        page = document.new_page()
        page.insert_text((72, 72), f"Strona {index + 1}")
    pdf_bytes = document.tobytes()
    document.close()

    provider = PyMuPdfRecentPagesProvider(recent_pages_count=3)
    extracted = provider.extract_recent_pages(pdf_bytes=pdf_bytes)

    assert extracted.page_count == 5
    assert len(extracted.recent_page_images_png) == 3
    assert all(
        isinstance(image, bytes) and image for image in extracted.recent_page_images_png
    )


def test_bedrock_json_parser_accepts_markdown_fences() -> None:
    raw = """```json
{
  "recent_notes_summary": "Uczeń cwiczyl wielomiany."
}
```"""

    parsed = _parse_insights_json(raw)

    assert parsed.recent_notes_summary == "Uczeń cwiczyl wielomiany."


class _FakeFilesResource:
    def __init__(self, by_parent: dict[str, list[dict[str, str]]]) -> None:
        self._by_parent = by_parent
        self._current_parent = ""

    def list(self, *, q: str, fields: str, pageSize: int):  # noqa: ARG002
        marker = "' in parents"
        self._current_parent = q.split(marker)[0].strip("'")
        return self

    def execute(self):
        return {"files": self._by_parent.get(self._current_parent, [])}


class _FakeDriveService:
    def __init__(self, by_parent: dict[str, list[dict[str, str]]]) -> None:
        self._files = _FakeFilesResource(by_parent)

    def files(self):
        return self._files


def test_find_notes_folder_searches_recursively() -> None:
    provider = GoogleDriveStudentNotesProvider(
        credentials_path="credentials.json",
        token_path="token.json",
        student_notes_folder_id="root",
    )
    fake_drive = _FakeDriveService(
        {
            "student-root": [
                {"id": "matematyka", "name": "Matematyka"},
                {"id": "informatyka", "name": "Informatyka"},
            ],
            "matematyka": [
                {"id": "notes-id", "name": "notatki"},
            ],
            "informatyka": [],
        }
    )

    notes_id = provider._find_notes_folder(  # pyright: ignore[reportPrivateUsage]
        drive_service=fake_drive,
        parent_folder_id="student-root",
    )

    assert notes_id == "notes-id"

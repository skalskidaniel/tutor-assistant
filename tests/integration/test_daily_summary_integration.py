from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
import os
from uuid import uuid4
from zoneinfo import ZoneInfo

import fitz
import pytest
from googleapiclient.discovery import build
from googleapiclient.http import MediaInMemoryUpload

from tutor import BedrockLessonInsightsProvider  # pyright: ignore[reportMissingImports]
from tutor import DailySummaryService  # pyright: ignore[reportMissingImports]
from tutor import GoogleCalendarLessonProvider  # pyright: ignore[reportMissingImports]
from tutor import GoogleDriveProvider  # pyright: ignore[reportMissingImports]
from tutor import GoogleDriveStudentNotesProvider  # pyright: ignore[reportMissingImports]
from tutor import GoogleMeetProvider  # pyright: ignore[reportMissingImports]
from tutor import MeetingSchedule  # pyright: ignore[reportMissingImports]
from tutor import Student  # pyright: ignore[reportMissingImports]
from tutor import PyMuPdfRecentPagesProvider  # pyright: ignore[reportMissingImports]
from tutor.core import (  # pyright: ignore[reportMissingImports]
    GOOGLE_ONBOARDING_SCOPES,
    load_google_credentials,
)


@pytest.mark.integration
def test_daily_summary_integration_real_google_and_bedrock() -> None:
    run_enabled = (
        os.getenv("GOOGLE_ENABLE_ALL_INTEGRATION_TESTS") == "1"
        or os.getenv("GOOGLE_ENABLE_DAILY_SUMMARY_INTEGRATION_TEST") == "1"
    )
    if not run_enabled:
        pytest.skip(
            "Test daily-summary jest opt-in. Ustaw GOOGLE_ENABLE_DAILY_SUMMARY_INTEGRATION_TEST=1 "
            "lub GOOGLE_ENABLE_ALL_INTEGRATION_TESTS=1."
        )

    credentials_path = os.getenv("GOOGLE_CREDENTIALS_PATH", "credentials.json")
    if not os.path.exists(credentials_path):
        pytest.skip("Brak credentials.json dla testu integracyjnego Google API.")

    parent_folder_id = os.getenv("GOOGLE_DRIVE_PARENT_FOLDER_ID")
    if not parent_folder_id:
        pytest.skip("Brak GOOGLE_DRIVE_PARENT_FOLDER_ID dla testu daily-summary.")

    start = datetime.now(ZoneInfo("Europe/Warsaw")) + timedelta(days=1)
    request = Student(
        first_name="Integracja",
        last_name=f"Daily{uuid4().hex[:6]}",
        email=os.getenv("GOOGLE_TEST_STUDENT_EMAIL", "integracja.test@example.com"),
        phone="+48500100200",
    )

    meet_provider = GoogleMeetProvider(
        schedule=MeetingSchedule(
            meeting_date=start.date(),
            hour=start.hour,
            minute=start.minute,
            recurrence="none",
        )
    )
    drive_provider = GoogleDriveProvider(parent_folder_id=parent_folder_id)

    try:
        drive_provider.create_student_workspace(request)
        meet_provider.create_personal_meeting(request)

        workspace_id = getattr(drive_provider, "_last_created_workspace_id", None)
        assert isinstance(workspace_id, str) and workspace_id

        _upload_notes_pdf(
            workspace_id=workspace_id,
            pdf_name="wielomiany.pdf",
            pdf_bytes=_build_test_pdf_bytes(),
        )

        service = DailySummaryService(
            calendar_provider=GoogleCalendarLessonProvider(
                calendar_id="primary",
                include_drive_scope=True,
            ),
            notes_provider=GoogleDriveStudentNotesProvider(
                parent_folder_id=parent_folder_id,
            ),
            pdf_recent_pages_provider=PyMuPdfRecentPagesProvider(recent_pages_count=3),
            insights_provider=BedrockLessonInsightsProvider(),
        )
        result = service.build_summary_for_day(target_date=start.date())
    finally:
        meet_provider.delete_last_created_meeting()
        drive_provider.delete_last_created_workspace()

    matching = [
        lesson
        for lesson in result.lesson_summaries
        if lesson.student_name == request.full_name
    ]
    assert matching, "Nie znaleziono podsumowania dla testowego ucznia."

    lesson = matching[0]
    assert lesson.source_pdf_name == "wielomiany.pdf"
    assert lesson.recent_notes_summary.strip()


def _upload_notes_pdf(*, workspace_id: str, pdf_name: str, pdf_bytes: bytes) -> None:
    credentials_path = os.getenv("GOOGLE_CREDENTIALS_PATH", "credentials.json")
    token_path = os.getenv("GOOGLE_TOKEN_PATH", "token.json")
    credentials = load_google_credentials(
        credentials_path=Path(credentials_path),
        token_path=Path(token_path),
        scopes=GOOGLE_ONBOARDING_SCOPES,
    )
    drive_service = build("drive", "v3", credentials=credentials)

    notes_folder_id = _find_notes_folder_id(
        drive_service=drive_service, workspace_id=workspace_id
    )
    drive_service.files().create(
        body={
            "name": pdf_name,
            "parents": [notes_folder_id],
            "mimeType": "application/pdf",
        },
        media_body=MediaInMemoryUpload(pdf_bytes, mimetype="application/pdf"),
        fields="id",
    ).execute()


def _find_notes_folder_id(*, drive_service, workspace_id: str) -> str:
    query = (
        f"'{workspace_id}' in parents and "
        "mimeType='application/vnd.google-apps.folder' and trashed=false"
    )
    response = (
        drive_service.files()
        .list(
            q=query,
            fields="files(id, name)",
        )
        .execute()
    )
    for item in response.get("files", []):
        folder_id = item.get("id")
        name = item.get("name")
        if isinstance(folder_id, str) and isinstance(name, str) and name == "notatki":
            return folder_id

    raise RuntimeError("Nie znaleziono folderu 'notatki' w testowym workspace.")


def _build_test_pdf_bytes() -> bytes:
    doc = fitz.open()
    page1 = doc.new_page()
    page1.insert_text((72, 72), "Rownania liniowe: 3 zadania rozwiazane")
    page2 = doc.new_page()
    page2.insert_text((72, 72), "Funkcja kwadratowa: 2 zadania rozwiazane")
    page3 = doc.new_page()
    page3.insert_text((72, 72), "Wielomiany: notatki z ostatniej lekcji")
    page4 = doc.new_page()
    page4.insert_text((72, 72), "Wielomiany: dalszy ciag notatek")
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes

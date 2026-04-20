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

from tutor_assistant import BedrockHomeworkMatcher  # pyright: ignore[reportMissingImports]
from tutor_assistant import BedrockLessonInsightsProvider  # pyright: ignore[reportMissingImports]
from tutor_assistant import GoogleCalendarLessonProvider  # pyright: ignore[reportMissingImports]
from tutor_assistant import GoogleDriveHomeworkProvider  # pyright: ignore[reportMissingImports]
from tutor_assistant import GoogleDriveProvider  # pyright: ignore[reportMissingImports]
from tutor_assistant import GoogleDriveStudentNotesProvider  # pyright: ignore[reportMissingImports]
from tutor_assistant import GoogleMeetProvider  # pyright: ignore[reportMissingImports]
from tutor_assistant import HomeworkService  # pyright: ignore[reportMissingImports]
from tutor_assistant import MeetingSchedule  # pyright: ignore[reportMissingImports]
from tutor_assistant import NewStudentRequest  # pyright: ignore[reportMissingImports]
from tutor_assistant import PyMuPdfRecentPagesProvider  # pyright: ignore[reportMissingImports]
from tutor_assistant.core import (  # pyright: ignore[reportMissingImports]
    GOOGLE_ONBOARDING_SCOPES,
    load_google_credentials,
)


@pytest.mark.integration
def test_homework_upload_integration_real_google_and_bedrock() -> None:
    run_enabled = (
        os.getenv("GOOGLE_ENABLE_ALL_INTEGRATION_TESTS") == "1"
        or os.getenv("GOOGLE_ENABLE_HOMEWORK_INTEGRATION_TEST") == "1"
    )
    if not run_enabled:
        pytest.skip(
            "Test use case 5 jest opt-in. Ustaw GOOGLE_ENABLE_HOMEWORK_INTEGRATION_TEST=1 "
            "lub GOOGLE_ENABLE_ALL_INTEGRATION_TESTS=1."
        )

    credentials_path = os.getenv("GOOGLE_CREDENTIALS_PATH", "credentials.json")
    if not os.path.exists(credentials_path):
        pytest.skip("Brak credentials.json dla testu integracyjnego Google API.")

    parent_folder_id = os.getenv("GOOGLE_DRIVE_PARENT_FOLDER_ID")
    if not parent_folder_id:
        pytest.skip("Brak GOOGLE_DRIVE_PARENT_FOLDER_ID dla testu use case 5.")

    homework_db_root_id = os.getenv("GOOGLE_HOMEWORK_DATABASE_FOLDER_ID")
    if not homework_db_root_id:
        pytest.skip("Brak GOOGLE_HOMEWORK_DATABASE_FOLDER_ID dla testu use case 5.")

    start = datetime.now(ZoneInfo("Europe/Warsaw")) + timedelta(days=1)
    token = uuid4().hex[:8]
    request = NewStudentRequest(
        first_name="Integracja",
        last_name=f"Homework{token}",
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

    drive_service = _build_drive_service()
    temp_homework_db_id: str | None = None
    try:
        drive_provider.create_student_workspace(request)
        meet_provider.create_personal_meeting(request)

        workspace_id = getattr(drive_provider, "_last_created_workspace_id", None)
        assert isinstance(workspace_id, str) and workspace_id

        _upload_notes_pdf(
            drive_service=drive_service,
            workspace_id=workspace_id,
            pdf_name=f"notatki-{token}.pdf",
            pdf_bytes=_build_notes_pdf_bytes(topic_token=token),
        )

        temp_homework_db_id = _create_folder(
            drive_service=drive_service,
            parent_id=homework_db_root_id,
            folder_name=f"test-homework-db-{token}",
        )
        homework_name = f"zadanie-{token}.pdf"
        _upload_pdf(
            drive_service=drive_service,
            parent_folder_id=temp_homework_db_id,
            file_name=homework_name,
            pdf_bytes=_build_homework_pdf_bytes(topic_token=token),
        )

        service = HomeworkService(
            calendar_provider=GoogleCalendarLessonProvider(
                calendar_id="primary",
                include_drive_scope=True,
            ),
            notes_provider=GoogleDriveStudentNotesProvider(
                parent_folder_id=parent_folder_id,
            ),
            pdf_recent_pages_provider=PyMuPdfRecentPagesProvider(recent_pages_count=3),
            insights_provider=BedrockLessonInsightsProvider(),
            homework_drive_provider=GoogleDriveHomeworkProvider(
                parent_folder_id=parent_folder_id,
                homework_database_folder_id=temp_homework_db_id,
            ),
            homework_matcher=BedrockHomeworkMatcher(),
        )
        result = service.upload_homework_for_day(target_date=start.date())
    finally:
        if temp_homework_db_id:
            drive_service.files().delete(fileId=temp_homework_db_id).execute()
        meet_provider.delete_last_created_meeting()
        drive_provider.delete_last_created_workspace()

    matching = [
        assignment
        for assignment in result.assignments
        if assignment.student_name == request.full_name
    ]
    assert matching, "Nie znaleziono wyniku uploadu zadania dla testowego ucznia."

    assignment = matching[0]
    assert assignment.status == "uploaded"
    assert assignment.selected_homework_name == homework_name
    assert assignment.uploaded_homework_name == homework_name


def _build_drive_service():
    credentials_path = os.getenv("GOOGLE_CREDENTIALS_PATH", "credentials.json")
    token_path = os.getenv("GOOGLE_TOKEN_PATH", "token.json")
    credentials = load_google_credentials(
        credentials_path=Path(credentials_path),
        token_path=Path(token_path),
        scopes=GOOGLE_ONBOARDING_SCOPES,
    )
    return build("drive", "v3", credentials=credentials)


def _upload_notes_pdf(*, drive_service, workspace_id: str, pdf_name: str, pdf_bytes: bytes) -> None:
    notes_folder_id = _find_child_folder_id(
        drive_service=drive_service,
        parent_folder_id=workspace_id,
        child_name="notatki",
    )
    _upload_pdf(
        drive_service=drive_service,
        parent_folder_id=notes_folder_id,
        file_name=pdf_name,
        pdf_bytes=pdf_bytes,
    )


def _find_child_folder_id(*, drive_service, parent_folder_id: str, child_name: str) -> str:
    query = (
        f"'{parent_folder_id}' in parents and "
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
        if isinstance(folder_id, str) and isinstance(name, str) and name == child_name:
            return folder_id

    raise RuntimeError(f"Nie znaleziono folderu '{child_name}' pod {parent_folder_id}.")


def _create_folder(*, drive_service, parent_id: str, folder_name: str) -> str:
    created = (
        drive_service.files()
        .create(
            body={
                "name": folder_name,
                "parents": [parent_id],
                "mimeType": "application/vnd.google-apps.folder",
            },
            fields="id",
        )
        .execute()
    )
    folder_id = created.get("id")
    if not isinstance(folder_id, str) or not folder_id:
        raise RuntimeError("Drive API nie zwrocilo identyfikatora folderu testowego.")
    return folder_id


def _upload_pdf(*, drive_service, parent_folder_id: str, file_name: str, pdf_bytes: bytes) -> None:
    drive_service.files().create(
        body={
            "name": file_name,
            "parents": [parent_folder_id],
            "mimeType": "application/pdf",
        },
        media_body=MediaInMemoryUpload(pdf_bytes, mimetype="application/pdf"),
        fields="id",
    ).execute()


def _build_notes_pdf_bytes(*, topic_token: str) -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text(
        (72, 72),
        (
            "Ostatnia lekcja: rozwiazywanie zadan typu "
            f"zadanie-{topic_token}.pdf i trening podobnych przykladow."
        ),
    )
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def _build_homework_pdf_bytes(*, topic_token: str) -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), f"Praca domowa testowa: zadanie-{topic_token}.pdf")
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes

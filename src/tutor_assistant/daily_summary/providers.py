"""Providers and integrations for daily summary flow."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
import base64
import json
import os
from typing import Any, Protocol, cast

import boto3
import fitz
from botocore.exceptions import BotoCoreError, ClientError
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from pydantic import BaseModel, ConfigDict, Field

from tutor_assistant.core import (
    GOOGLE_ONBOARDING_SCOPES,
    load_google_credentials,
    slugify,
)

from .models import ExtractedRecentPages, LatestNotesPdf, LessonInsights


class StudentNotesProvider(Protocol):
    def get_latest_notes_pdf(self, *, student_name: str) -> LatestNotesPdf | None: ...


class PdfRecentPagesProvider(Protocol):
    def extract_recent_pages(self, *, pdf_bytes: bytes) -> ExtractedRecentPages: ...


class LessonInsightsProvider(Protocol):
    def analyze_lesson_notes(
        self, *, extracted_pages: ExtractedRecentPages
    ) -> LessonInsights: ...


class GoogleDriveStudentNotesProvider:
    def __init__(
        self,
        *,
        credentials_path: str | Path | None = None,
        token_path: str | Path | None = None,
        parent_folder_id: str | None = None,
    ) -> None:
        self._credentials_path = Path(
            credentials_path or os.getenv("GOOGLE_CREDENTIALS_PATH", "credentials.json")
        )
        self._token_path = Path(
            token_path or os.getenv("GOOGLE_TOKEN_PATH", "token.json")
        )
        self._parent_folder_id = parent_folder_id or os.getenv(
            "GOOGLE_DRIVE_PARENT_FOLDER_ID"
        )
        if not self._parent_folder_id:
            raise ValueError(
                "Brak folderu nadrzednego. Ustaw GOOGLE_DRIVE_PARENT_FOLDER_ID "
                "lub przekaz --drive-parent-folder-id."
            )

    def get_latest_notes_pdf(self, *, student_name: str) -> LatestNotesPdf | None:
        drive_service = self._build_drive_service()
        student_folder = self._find_student_folder(
            drive_service=drive_service,
            student_name=student_name,
        )
        if student_folder is None:
            return None

        notes_folder = self._find_notes_folder(
            drive_service=drive_service,
            parent_folder_id=student_folder,
        )
        if notes_folder is None:
            return None

        pdf_metadata = self._find_latest_pdf(
            drive_service=drive_service,
            notes_folder_id=notes_folder,
        )
        if pdf_metadata is None:
            return None

        file_id, file_name, modified_time = pdf_metadata
        try:
            blob = drive_service.files().get_media(fileId=file_id).execute()
        except HttpError as exc:
            raise RuntimeError(
                f"Nie udalo sie pobrac pliku PDF dla ucznia {student_name}. "
                f"Szczegoly: {_format_http_error(exc)}"
            ) from exc

        if not isinstance(blob, bytes):
            raise RuntimeError(
                "Drive API zwrocilo nieoczekiwany format zawartosci pliku."
            )

        return LatestNotesPdf(
            file_name=file_name,
            file_id=file_id,
            pdf_bytes=blob,
            modified_time=modified_time,
        )

    def _build_drive_service(self):
        credentials = load_google_credentials(
            credentials_path=self._credentials_path,
            token_path=self._token_path,
            scopes=GOOGLE_ONBOARDING_SCOPES,
        )
        return build("drive", "v3", credentials=credentials)

    def _find_student_folder(self, *, drive_service, student_name: str) -> str | None:
        expected_slug = slugify(student_name)
        query = (
            f"'{self._parent_folder_id}' in parents and "
            "mimeType='application/vnd.google-apps.folder' and trashed=false"
        )
        try:
            response = (
                drive_service.files()
                .list(
                    q=query,
                    fields="files(id, name)",
                    pageSize=200,
                )
                .execute()
            )
        except HttpError as exc:
            raise RuntimeError(
                "Nie udalo sie pobrac folderow uczniow z Google Drive. "
                f"Szczegoly: {_format_http_error(exc)}"
            ) from exc

        candidates: list[tuple[str, str]] = []
        for item in response.get("files", []):
            folder_id = item.get("id")
            folder_name = item.get("name")
            if isinstance(folder_id, str) and isinstance(folder_name, str):
                candidates.append((folder_id, folder_name))

        for folder_id, folder_name in candidates:
            if slugify(folder_name) == expected_slug:
                return folder_id

        return None

    def _find_notes_folder(self, *, drive_service, parent_folder_id: str) -> str | None:
        queue = [parent_folder_id]
        visited: set[str] = set()

        while queue:
            folder_id = queue.pop(0)
            if folder_id in visited:
                continue
            visited.add(folder_id)

            query = (
                f"'{folder_id}' in parents and "
                "mimeType='application/vnd.google-apps.folder' and trashed=false"
            )
            try:
                response = (
                    drive_service.files()
                    .list(
                        q=query,
                        fields="files(id, name)",
                        pageSize=200,
                    )
                    .execute()
                )
            except HttpError as exc:
                raise RuntimeError(
                    "Nie udalo sie pobrac podfolderow ucznia z Google Drive. "
                    f"Szczegoly: {_format_http_error(exc)}"
                ) from exc

            for item in response.get("files", []):
                child_id = item.get("id")
                child_name = item.get("name")
                if not isinstance(child_id, str) or not isinstance(child_name, str):
                    continue
                if slugify(child_name) == "notatki":
                    return child_id
                queue.append(child_id)

        return None

    def _find_latest_pdf(
        self, *, drive_service, notes_folder_id: str
    ) -> tuple[str, str, datetime] | None:
        query = (
            f"'{notes_folder_id}' in parents and "
            "mimeType='application/pdf' and trashed=false"
        )
        try:
            response = (
                drive_service.files()
                .list(
                    q=query,
                    fields="files(id, name, modifiedTime)",
                    orderBy="modifiedTime desc",
                    pageSize=1,
                )
                .execute()
            )
        except HttpError as exc:
            raise RuntimeError(
                "Nie udalo sie pobrac listy PDF z folderu notatki. "
                f"Szczegoly: {_format_http_error(exc)}"
            ) from exc

        files = response.get("files", [])
        if not files:
            return None

        item = files[0]
        file_id = item.get("id")
        file_name = item.get("name")
        modified_time_raw = item.get("modifiedTime")
        if (
            not isinstance(file_id, str)
            or not isinstance(file_name, str)
            or not isinstance(modified_time_raw, str)
        ):
            raise RuntimeError("Drive API zwrocilo niepelne metadane pliku PDF.")

        modified_time = _parse_google_timestamp(modified_time_raw)
        return file_id, file_name, modified_time


class PyMuPdfRecentPagesProvider:
    def __init__(self, *, recent_pages_count: int = 3) -> None:
        if recent_pages_count < 1:
            raise ValueError("recent_pages_count musi byc wieksze od zera.")
        self._recent_pages_count = recent_pages_count

    def extract_recent_pages(self, *, pdf_bytes: bytes) -> ExtractedRecentPages:
        if not pdf_bytes:
            raise ValueError("PDF jest pusty.")

        try:
            document = fitz.open(stream=pdf_bytes, filetype="pdf")
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"Nie udalo sie odczytac PDF: {exc}") from exc

        with document:
            page_count = len(document)
            recent_images: list[bytes] = []
            recent_start = max(0, page_count - self._recent_pages_count)

            for index in range(recent_start, page_count):
                page = document.load_page(index)
                pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
                recent_images.append(pixmap.tobytes("png"))

        return ExtractedRecentPages(
            recent_page_images_png=tuple(recent_images),
            page_count=page_count,
        )


class _BedrockLessonInsights(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    recent_notes_summary: str = Field(min_length=1)


class BedrockLessonInsightsProvider:
    def __init__(
        self,
        *,
        model_id: str | None = None,
        region_name: str | None = None,
    ) -> None:
        self._model_id = model_id or os.getenv(
            "BEDROCK_MODEL_ID", "anthropic.claude-3-haiku-20240307-v1:0"
        )
        self._region_name = (
            region_name
            or os.getenv("AWS_REGION")
            or os.getenv("AWS_DEFAULT_REGION", "eu-central-1")
        )

    def analyze_lesson_notes(
        self, *, extracted_pages: ExtractedRecentPages
    ) -> LessonInsights:
        if not extracted_pages.recent_page_images_png:
            return LessonInsights(
                recent_notes_summary="Brak stron do analizy w notatkach PDF.",
            )

        client = boto3.client("bedrock-runtime", region_name=self._region_name)
        prompt = self._build_prompt()
        content_blocks: list[dict[str, object]] = [
            {
                "type": "text",
                "text": prompt,
            }
        ]
        for image_bytes in extracted_pages.recent_page_images_png:
            content_blocks.append(
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/png",
                        "data": base64.b64encode(image_bytes).decode("utf-8"),
                    },
                }
            )

        payload = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 800,
            "temperature": 0,
            "messages": [{"role": "user", "content": content_blocks}],
        }

        try:
            response = client.invoke_model(
                modelId=self._model_id,
                body=json.dumps(payload),
                contentType="application/json",
                accept="application/json",
            )
        except (BotoCoreError, ClientError) as exc:
            raise RuntimeError(f"Nie udalo sie wywolac AWS Bedrock: {exc}") from exc

        raw_body = response.get("body")
        if raw_body is None:
            raise RuntimeError("AWS Bedrock nie zwrocil tresci odpowiedzi.")

        body_text = raw_body.read().decode("utf-8")
        try:
            parsed = json.loads(body_text)
        except json.JSONDecodeError as exc:
            raise RuntimeError("Niepoprawny JSON z AWS Bedrock.") from exc

        message_text = _extract_bedrock_text(parsed)
        insights = _parse_insights_json(message_text)
        return LessonInsights(
            recent_notes_summary=insights.recent_notes_summary,
        )

    @staticmethod
    def _build_prompt() -> str:
        return (
            "Jestes asystentem nauczyciela matematyki. Otrzymasz obrazy 3 ostatnich "
            "stron notatek ucznia. Odczytaj tresc (takze reczne pismo) i przygotuj "
            "zwiezle podsumowanie ostatnio przerobionego materialu. "
            "Odpowiedz tylko po polsku i zwroc "
            "wylacznie poprawny JSON bez markdownu i bez dodatkowego tekstu.\n\n"
            "Wymagany format JSON:\n"
            "{\n"
            '  "recent_notes_summary": "krotkie podsumowanie max 4 zdania"\n'
            "}\n\n"
            "Zasady:\n"
            "1) Pole recent_notes_summary oprzyj TYLKO na przeslanych obrazach stron.\n"
            "2) Jesli nie da sie odczytac tresci, zwroc recent_notes_summary='Brak danych.'"
        )


PyMuPdfTextProvider = PyMuPdfRecentPagesProvider


def _extract_bedrock_text(payload: object) -> str:
    if not isinstance(payload, dict):
        raise RuntimeError("Nieoczekiwany format odpowiedzi Bedrock.")

    content_raw = payload.get("content")
    if not isinstance(content_raw, list):
        raise RuntimeError("Brak pola content w odpowiedzi Bedrock.")

    content = cast(list[object], content_raw)

    for block in content:
        if not isinstance(block, dict):
            continue
        text = block.get("text")
        if isinstance(text, str) and text.strip():
            return text

    raise RuntimeError("Brak tekstu odpowiedzi modelu Bedrock.")


def _parse_insights_json(raw_text: str) -> _BedrockLessonInsights:
    cleaned = raw_text.strip()
    if cleaned.startswith("```"):
        cleaned = _strip_markdown_fence(cleaned)

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            "Model Bedrock zwrocil niepoprawny JSON z podsumowaniem lekcji."
        ) from exc

    if not isinstance(parsed, dict):
        raise RuntimeError("Model Bedrock zwrocil JSON w nieoczekiwanym formacie.")

    return _BedrockLessonInsights.model_validate(cast(dict[str, Any], parsed))


def _strip_markdown_fence(text: str) -> str:
    parts = text.split("\n")
    if len(parts) >= 3 and parts[0].startswith("```") and parts[-1].startswith("```"):
        return "\n".join(parts[1:-1]).strip()
    return text


def _parse_google_timestamp(value: str) -> datetime:
    if value.endswith("Z"):
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    return datetime.fromisoformat(value)


def _format_http_error(error: HttpError) -> str:
    status = getattr(error.resp, "status", "unknown")
    reason = getattr(error, "reason", None)
    if isinstance(reason, str) and reason:
        return f"HTTP {status}: {reason}"
    return f"HTTP {status}: {error}"

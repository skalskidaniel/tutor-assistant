from __future__ import annotations

from datetime import datetime
from pathlib import Path
import base64
import json
import os
from typing import Any, Protocol, cast

import boto3
import pymupdf
from botocore.exceptions import BotoCoreError, ClientError
from googleapiclient.errors import HttpError
from pydantic import BaseModel, ConfigDict, Field

from tutor.core import (
    slugify,
    extract_bedrock_text,
    format_http_error,
    resolve_required_path,
)
from tutor.drive import build_drive_service, parse_google_timestamp

from .models import ExtractedRecentPages, LatestNotesPdf, LessonInsights

MAX_BEDROCK_IMAGE_DIMENSION = 8000


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
        credentials_path: str | Path | None = "credentials.json",
        token_path: str | Path | None = "token.json",
        student_notes_folder_id: str | None = None,
    ) -> None:
        self._credentials_path = resolve_required_path(
            explicit_path=credentials_path,
            env_var_name="GOOGLE_CREDENTIALS_PATH"
        )
        self._token_path = resolve_required_path(
            explicit_path=token_path,
            env_var_name="GOOGLE_TOKEN_PATH"
        )
        self._parent_folder_id = student_notes_folder_id or os.getenv(
            "GOOGLE_DRIVE_STUDENT_NOTES_FOLDER_ID"
        )
        if not self._parent_folder_id:
            raise ValueError(
                "Missing GOOGLE_DRIVE_STUDENT_NOTES_FOLDER_ID. "
                "You may use --student-notes-folder-id."
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
                f"Error downloading PDF file for student {student_name}. "
                f"Details: {format_http_error(exc)}"
            ) from exc

        if not isinstance(blob, bytes):
            raise RuntimeError(
                "Drive API returned unexpected file content format."
            )

        return LatestNotesPdf(
            file_name=file_name,
            file_id=file_id,
            pdf_bytes=blob,
            modified_time=modified_time,
        )

    def _build_drive_service(self):
        return build_drive_service(
            credentials_path=self._credentials_path,
            token_path=self._token_path,
        )

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
                "Error downloading student folders from Google Drive. "
                f"Details: {format_http_error(exc)}"
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
                    "Error downloading student's child folders from Google Drive. "
                    f"Details: {format_http_error(exc)}"
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
                "Error downloading PDF list from notes folder. "
                f"Details: {format_http_error(exc)}"
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
            raise RuntimeError("Drive API returned incomplete PDF file metadata.")

        modified_time = parse_google_timestamp(modified_time_raw)
        return file_id, file_name, modified_time


class PyMuPdfRecentPagesProvider:
    def __init__(
        self,
        *,
        recent_pages_count: int = 3,
        max_total_image_bytes: int = 2_500_000,
    ) -> None:
        if recent_pages_count < 1:
            raise ValueError("recent_pages_count must be greater than zero.")
        if max_total_image_bytes < 100_000:
            raise ValueError("max_total_image_bytes is too small.")
        self._recent_pages_count = recent_pages_count
        self._max_total_image_bytes = max_total_image_bytes

    def extract_recent_pages(self, *, pdf_bytes: bytes) -> ExtractedRecentPages:
        if not pdf_bytes:
            raise ValueError("PDF is empty.")

        try:
            document = pymupdf.open(stream=pdf_bytes, filetype="pdf")
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"Error reading PDF: {exc}") from exc

        with document:
            page_count = len(document)
            recent_start = max(0, page_count - self._recent_pages_count)
            recent_indices = list(range(recent_start, page_count))

            recent_images: list[bytes] = []
            for scale in (1.0, 0.85, 0.7, 0.55):
                candidate = self._render_recent_pages(
                    document=document,
                    page_indices=recent_indices,
                    scale=scale,
                )
                recent_images = candidate
                if (
                    sum(len(image) for image in candidate)
                    <= self._max_total_image_bytes
                ):
                    break

        return ExtractedRecentPages(
            recent_page_images_png=tuple(recent_images),
            page_count=page_count,
        )

    @staticmethod
    def _render_recent_pages(
        *,
        document,
        page_indices: list[int],
        scale: float,
    ) -> list[bytes]:
        images: list[bytes] = []
        for index in page_indices:
            page = document.load_page(index)
            adjusted_scale = _scale_for_dimension_limit(page=page, base_scale=scale)
            matrix = pymupdf.Matrix(adjusted_scale, adjusted_scale)
            pixmap = page.get_pixmap(
                matrix=matrix, colorspace=pymupdf.csGRAY, alpha=False
            )
            images.append(pixmap.tobytes("png"))
        return images


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
            "BEDROCK_INSIGHTS_MODEL_ID",
            "anthropic.claude-3-haiku-20240307-v1:0",
        )
        self._region_name = (
            region_name
            or os.getenv("AWS_REGION")
            or os.getenv("AWS_DEFAULT_REGION", "eu-central-1")
        )

    def analyze_lesson_notes(
        self, *, extracted_pages: ExtractedRecentPages
    ) -> LessonInsights:
        images = list(extracted_pages.recent_page_images_png)
        if not images:
            return LessonInsights(
                recent_notes_summary="No pages to analyze in PDF notes.",
            )

        client = boto3.client("bedrock-runtime", region_name=self._region_name)
        prompt = self._build_prompt()

        while images:
            content_blocks: list[dict[str, object]] = [
                {
                    "type": "text",
                    "text": prompt,
                }
            ]
            for image_bytes in images:
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
                break
            except (BotoCoreError, ClientError) as exc:
                details = str(exc)
                if "Input is too long" in details and len(images) > 1:
                    images = images[1:]
                    continue
                raise RuntimeError(f"Error calling AWS Bedrock: {exc}") from exc
        else:
            raise RuntimeError(
                "Error preparing correct input for Bedrock."
            )

        raw_body = response.get("body")
        if raw_body is None:
            raise RuntimeError("AWS Bedrock did not return response content.")

        body_text = raw_body.read().decode("utf-8")
        try:
            parsed = json.loads(body_text)
        except json.JSONDecodeError as exc:
            raise RuntimeError("Invalid JSON from AWS Bedrock.") from exc

        message_text = extract_bedrock_text(parsed)
        insights = _parse_insights_json(message_text)
        return LessonInsights(
            recent_notes_summary=insights.recent_notes_summary,
        )

    @staticmethod
    def _build_prompt() -> str:
        return (
            "Jesteś asystentem nauczyciela matematyki. Otrzymasz obrazy 3 ostatnich "
            "stron notatek ucznia. Odczytaj treść (także ręczne pismo) i przygotuj "
            "zwięźle podsumowanie ostatnio przerobionego material (max 3 zdania). "
            "Pisz w prostym języku."
            "Odpowiedz tylko po polsku i zwróć "
            "wyłącznie poprawny JSON bez markdown i bez dodatkowego tekstu.\n\n"
            "Wymagany format JSON:\n"
            "{\n"
            '  "recent_notes_summary": "krótkie podsumowanie max 4 zdania"\n'
            "}\n\n"
            "Zasady:\n"
            "1) Pole recent_notes_summary oprzyj TYLKO na przesilanych obrazach stron.\n"
            "2) Jeśli nie da sie odczytać treści, zwróć recent_notes_summary='Brak danych.'"
        )


PyMuPdfTextProvider = PyMuPdfRecentPagesProvider


def _parse_insights_json(raw_text: str) -> _BedrockLessonInsights:
    cleaned = raw_text.strip()
    if cleaned.startswith("```"):
        cleaned = _strip_markdown_fence(cleaned)

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            "Model Bedrock returned invalid JSON with lesson summary."
        ) from exc

    if not isinstance(parsed, dict):
        raise RuntimeError("Model Bedrock returned JSON in unexpected format.")

    return _BedrockLessonInsights.model_validate(cast(dict[str, Any], parsed))


def _strip_markdown_fence(text: str) -> str:
    parts = text.split("\n")
    if len(parts) >= 3 and parts[0].startswith("```") and parts[-1].startswith("```"):
        return "\n".join(parts[1:-1]).strip()
    return text


def _scale_for_dimension_limit(*, page, base_scale: float) -> float:
    max_page_dimension = max(page.rect.width, page.rect.height)
    allowed_scale = MAX_BEDROCK_IMAGE_DIMENSION / max_page_dimension
    return max(0.1, min(base_scale, allowed_scale))

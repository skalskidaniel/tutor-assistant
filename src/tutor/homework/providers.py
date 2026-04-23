from __future__ import annotations

from pathlib import Path
import json
import os
from typing import Any, Protocol, cast

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from googleapiclient.errors import HttpError
from pydantic import BaseModel, ConfigDict

from tutor.core import (
    slugify,
    resolve_required_path,
    extract_bedrock_text,
    format_http_error,
)
from tutor.drive import build_drive_service

from .models import DriveFile


class HomeworkDriveProvider(Protocol):
    def list_homework_database_files(self) -> list[DriveFile]: ...

    def find_student_homework_folder(self, *, student_name: str) -> str | None: ...

    def copy_homework_to_student(
        self,
        *,
        source_file_id: str,
        source_file_name: str,
        target_homework_folder_id: str,
    ) -> DriveFile: ...


class HomeworkMatcher(Protocol):
    def select_homework_name(
        self,
        *,
        notes_summary: str,
        available_homework_names: tuple[str, ...],
    ) -> str | None: ...


class GoogleDriveHomeworkProvider:
    def __init__(
        self,
        *,
        credentials_path: str | Path | None = "credentials.json",
        token_path: str | Path | None = "token.json",
        parent_folder_id: str | None = None,
        homework_database_folder_id: str | None = None,
    ) -> None:
        self._credentials_path = resolve_required_path(
            explicit_path=credentials_path,
            env_var_name="GOOGLE_CREDENTIALS_PATH"
        )
        self._token_path = resolve_required_path(
            explicit_path=token_path,
            env_var_name="GOOGLE_TOKEN_PATH"
        )
        self._parent_folder_id = parent_folder_id or os.getenv(
            "GOOGLE_DRIVE_PARENT_FOLDER_ID"
        )
        self._homework_database_folder_id = homework_database_folder_id or os.getenv(
            "GOOGLE_HOMEWORK_DATABASE_FOLDER_ID"
        )
        if not self._parent_folder_id:
            raise ValueError(
                "GOOGLE_DRIVE_PARENT_FOLDER_ID is missing. "
                "You may use --drive-parent-folder-id."
            )
        if not self._homework_database_folder_id:
            raise ValueError(
                "GOOGLE_HOMEWORK_DATABASE_FOLDER_ID is missing. "
                "You may use --homework-db-folder-id."
            )

    def list_homework_database_files(self) -> list[DriveFile]:
        drive_service = self._build_drive_service()
        query = (
            f"'{self._homework_database_folder_id}' in parents and "
            "mimeType!='application/vnd.google-apps.folder' and trashed=false"
        )

        files: list[DriveFile] = []
        page_token: str | None = None
        try:
            while True:
                response = (
                    drive_service.files()
                    .list(
                        q=query,
                        fields="nextPageToken, files(id, name)",
                        pageToken=page_token,
                    )
                    .execute()
                )
                for item in response.get("files", []):
                    file_id = item.get("id")
                    file_name = item.get("name")
                    if isinstance(file_id, str) and isinstance(file_name, str):
                        files.append(DriveFile(id=file_id, name=file_name))

                page_token = response.get("nextPageToken")
                if not page_token:
                    break
        except HttpError as exc:
            raise RuntimeError(
                "Error downloading files from homework database. "
                f"Details: {format_http_error(exc)}"
            ) from exc

        return files

    def find_student_homework_folder(self, *, student_name: str) -> str | None:
        drive_service = self._build_drive_service()
        student_folder_id = self._find_student_folder_id(
            drive_service=drive_service,
            student_name=student_name,
        )
        if student_folder_id is None:
            return None

        return self._find_homework_folder_id(
            drive_service=drive_service,
            student_folder_id=student_folder_id,
        )

    def copy_homework_to_student(
        self,
        *,
        source_file_id: str,
        source_file_name: str,
        target_homework_folder_id: str,
    ) -> DriveFile:
        drive_service = self._build_drive_service()
        try:
            created = (
                drive_service.files()
                .copy(
                    fileId=source_file_id,
                    body={
                        "name": source_file_name,
                        "parents": [target_homework_folder_id],
                    },
                    fields="id, name",
                )
                .execute()
            )
        except HttpError as exc:
            raise RuntimeError(
                "Error copying homework to student's folder. "
                f"Details: {format_http_error(exc)}"
            ) from exc

        copied_id = created.get("id")
        copied_name = created.get("name")
        if not isinstance(copied_id, str) or not isinstance(copied_name, str):
            raise RuntimeError(
                "Drive API returned faulty metadata."
            )

        return DriveFile(id=copied_id, name=copied_name)

    def _build_drive_service(self):
        return build_drive_service(
            credentials_path=self._credentials_path,
            token_path=self._token_path,
        )

    def _find_student_folder_id(
        self, *, drive_service, student_name: str
    ) -> str | None:
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
                "Error downloading student's folder. "
                f"Details: {format_http_error(exc)}"
            ) from exc

        for item in response.get("files", []):
            folder_id = item.get("id")
            folder_name = item.get("name")
            if (
                isinstance(folder_id, str)
                and isinstance(folder_name, str)
                and slugify(folder_name) == expected_slug
            ):
                return folder_id

        return None

    def _find_homework_folder_id(
        self, *, drive_service, student_folder_id: str
    ) -> str | None:
        queue = [student_folder_id]
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
                    "Error downloading student's folder. "
                    f"Details: {format_http_error(exc)}"
                ) from exc

            for item in response.get("files", []):
                child_id = item.get("id")
                child_name = item.get("name")
                if not isinstance(child_id, str) or not isinstance(child_name, str):
                    continue
                if slugify(child_name).replace("_", "-") == "zadania-domowe":
                    return child_id
                queue.append(child_id)

        return None


class _HomeworkMatchResponse(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    selected_homework_name: str | None = None
    reason: str | None = None


class BedrockHomeworkMatcher:
    def __init__(
        self,
        *,
        model_id: str | None = None,
        region_name: str | None = None,
    ) -> None:
        self._model_id = model_id or os.getenv(
            "BEDROCK_HOMEWORK_MATCHER_MODEL_ID",
            "amazon.nova-micro-v1:0",
        )
        self._region_name = (
            region_name
            or os.getenv("AWS_REGION")
            or os.getenv("AWS_DEFAULT_REGION", "eu-central-1")
        )

    def select_homework_name(
        self,
        *,
        notes_summary: str,
        available_homework_names: tuple[str, ...],
    ) -> str | None:
        if not available_homework_names:
            return None

        client = boto3.client("bedrock-runtime", region_name=self._region_name)
        prompt = self._build_prompt(
            notes_summary=notes_summary,
            available_homework_names=available_homework_names,
        )

        payload = {
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "text": prompt,
                        }
                    ],
                }
            ],
        }

        try:
            response = client.invoke_model(
                modelId=self._model_id,
                body=json.dumps(payload),
                contentType="application/json",
                accept="application/json",
            )
        except (BotoCoreError, ClientError) as exc:
            raise RuntimeError(f"Error calling AWS Bedrock: {exc}") from exc

        raw_body = response.get("body")
        if raw_body is None:
            raise RuntimeError("AWS Bedrock return empty response.")

        body_text = raw_body.read().decode("utf-8")
        try:
            parsed = json.loads(body_text)
        except json.JSONDecodeError as exc:
            raise RuntimeError("AWS Bedrock returned faulty JSON.") from exc

        message_text = extract_bedrock_text(parsed)
        match = _parse_match_json(message_text)
        selected = match.selected_homework_name
        if not selected:
            return None

        resolved = _resolve_homework_name(
            selected_name=selected,
            available_names=available_homework_names,
        )
        return resolved

    @staticmethod
    def _build_prompt(
        *,
        notes_summary: str,
        available_homework_names: tuple[str, ...],
    ) -> str:
        available = "\n".join(f"- {name}" for name in available_homework_names)
        return (
            "Jesteś asystentem nauczyciela matematyki. Na podstawie podsumowania "
            "ostatniej lekcji wybierz jedno najlepsze zadanie domowe z listy. "
            "Możesz zwrócić tylko nazwę pliku, która znajduje sie na liście. "
            "Jeśli nic nie pasuje, zwróć null.\n\n"
            f"Podsumowanie lekcji:\n{notes_summary}\n\n"
            f"Dostępne pliki zadań domowych:\n{available}\n\n"
            "Odpowiedz tylko po polsku i zwróć wyłącznie poprawny JSON "
            "bez markdown i bez dodatkowego tekstu.\n\n"
            "Wymagany format JSON:\n"
            "{\n"
            '  "selected_homework_name": "dokładna nazwa pliku z listy" | null,\n'
            '  "reason": "krótkie uzasadnienie wyboru"\n'
            "}\n"
        )


def _parse_match_json(raw_text: str) -> _HomeworkMatchResponse:
    cleaned = raw_text.strip()
    if cleaned.startswith("```"):
        cleaned = _strip_markdown_fence(cleaned)

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            "Model Bedrock zwrocil niepoprawny JSON z wyborem zadania domowego."
        ) from exc

    if not isinstance(parsed, dict):
        raise RuntimeError("Model Bedrock zwrocil JSON w nieoczekiwanym formacie.")

    return _HomeworkMatchResponse.model_validate(cast(dict[str, Any], parsed))


def _strip_markdown_fence(text: str) -> str:
    parts = text.split("\n")
    if len(parts) >= 3 and parts[0].startswith("```") and parts[-1].startswith("```"):
        return "\n".join(parts[1:-1]).strip()
    return text


def _resolve_homework_name(
    *,
    selected_name: str,
    available_names: tuple[str, ...],
) -> str | None:
    for candidate in available_names:
        if candidate == selected_name:
            return candidate

    casefold_matches = [
        candidate
        for candidate in available_names
        if candidate.casefold() == selected_name.casefold()
    ]
    if len(casefold_matches) == 1:
        return casefold_matches[0]

    selected_normalized = _normalize_filename(selected_name)
    normalized_matches = [
        candidate
        for candidate in available_names
        if _normalize_filename(candidate) == selected_normalized
    ]
    if len(normalized_matches) == 1:
        return normalized_matches[0]

    return None


def _normalize_filename(filename: str) -> str:
    dot_index = filename.rfind(".")
    if dot_index <= 0:
        return slugify(filename)
    stem = filename[:dot_index]
    suffix = filename[dot_index:].lower()
    return f"{slugify(stem)}{suffix}"

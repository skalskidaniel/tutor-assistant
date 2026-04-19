"""Providers and integrations for vacation notifications flow."""

from __future__ import annotations

from email.message import EmailMessage
from pathlib import Path
import base64
import os
from typing import Protocol

from googleapiclient.errors import HttpError

from googleapiclient.discovery import build

from tutor_assistant.core import GOOGLE_VACATION_SCOPES, load_google_credentials


class StudentEmailProvider(Protocol):
    def send_vacation_notice(
        self,
        *,
        recipient_email: str,
        subject: str,
        body: str,
    ) -> None: ...


class InMemoryEmailProvider:
    def __init__(self) -> None:
        self.sent_messages: list[tuple[str, str, str]] = []

    def send_vacation_notice(
        self,
        *,
        recipient_email: str,
        subject: str,
        body: str,
    ) -> None:
        self.sent_messages.append((recipient_email, subject, body))


class GmailProvider:
    def __init__(
        self,
        *,
        credentials_path: str | Path | None = None,
        token_path: str | Path | None = None,
        sender_email: str | None = None,
    ) -> None:
        self._credentials_path = Path(
            credentials_path or os.getenv("GOOGLE_CREDENTIALS_PATH", "credentials.json")
        )
        self._token_path = Path(
            token_path or os.getenv("GOOGLE_TOKEN_PATH", "token.json")
        )
        self._sender_email = sender_email or os.getenv("GMAIL_SENDER_EMAIL", "me")

    def send_vacation_notice(
        self,
        *,
        recipient_email: str,
        subject: str,
        body: str,
    ) -> None:
        gmail_service = self._build_gmail_service()

        message = EmailMessage()
        message["To"] = recipient_email
        message["From"] = self._sender_email
        message["Subject"] = subject
        message.set_content(body)

        encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")
        payload = {"raw": encoded_message}

        try:
            gmail_service.users().messages().send(userId="me", body=payload).execute()
        except HttpError as exc:
            raise RuntimeError(
                f"Nie udalo sie wyslac e-maila do {recipient_email}. "
                f"Szczegoly: {_format_http_error(exc)}"
            ) from exc

    def _build_gmail_service(self):
        credentials = load_google_credentials(
            credentials_path=self._credentials_path,
            token_path=self._token_path,
            scopes=GOOGLE_VACATION_SCOPES,
        )
        return build("gmail", "v1", credentials=credentials)


def _format_http_error(error: HttpError) -> str:
    status = getattr(error.resp, "status", "unknown")
    reason = getattr(error, "reason", None)
    if isinstance(reason, str) and reason:
        return f"HTTP {status}: {reason}"
    return f"HTTP {status}: {error}"

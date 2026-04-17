"""Google authentication helpers shared across use cases."""

from __future__ import annotations

from pathlib import Path
from typing import cast

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

CALENDAR_SCOPES = ("https://www.googleapis.com/auth/calendar.events",)
DRIVE_SCOPES = ("https://www.googleapis.com/auth/drive",)
GOOGLE_ONBOARDING_SCOPES = CALENDAR_SCOPES + DRIVE_SCOPES


def load_google_credentials(
    *,
    credentials_path: Path,
    token_path: Path,
    scopes: tuple[str, ...],
) -> Credentials:
    credentials: Credentials | None = None

    if token_path.exists():
        credentials = cast(
            Credentials,
            Credentials.from_authorized_user_file(str(token_path), scopes),
        )

    if (
        credentials
        and credentials.valid
        and _credentials_cover_scopes(credentials, scopes)
    ):
        return credentials

    if (
        credentials
        and credentials.expired
        and credentials.refresh_token
        and _credentials_cover_scopes(credentials, scopes)
    ):
        credentials.refresh(Request())
    else:
        if not credentials_path.exists():
            raise FileNotFoundError(
                f"Brak pliku credentials: {credentials_path}. "
                "Pobierz go z Google Cloud Console."
            )
        flow = InstalledAppFlow.from_client_secrets_file(str(credentials_path), scopes)
        credentials = cast(Credentials, flow.run_local_server(port=0))

    if credentials is None:
        raise RuntimeError(
            "Nie udalo sie uzyskac poprawnych danych uwierzytelniajacych Google."
        )

    token_path.write_text(credentials.to_json(), encoding="utf-8")
    return credentials


def _credentials_cover_scopes(
    credentials: Credentials, scopes: tuple[str, ...]
) -> bool:
    return credentials.has_scopes(list(scopes))

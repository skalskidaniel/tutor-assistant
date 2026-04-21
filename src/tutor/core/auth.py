from __future__ import annotations

from pathlib import Path
import json
import os
from typing import cast

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

CALENDAR_SCOPES = ("https://www.googleapis.com/auth/calendar.events",)
DRIVE_SCOPES = ("https://www.googleapis.com/auth/drive",)
GMAIL_SEND_SCOPES = ("https://www.googleapis.com/auth/gmail.send",)
GOOGLE_ONBOARDING_SCOPES = CALENDAR_SCOPES + DRIVE_SCOPES
GOOGLE_VACATION_SCOPES = CALENDAR_SCOPES + GMAIL_SEND_SCOPES
GOOGLE_CALENDAR_DRIVE_SCOPES = CALENDAR_SCOPES + DRIVE_SCOPES
DEFAULT_GOOGLE_AUTH_URI = "https://accounts.google.com/o/oauth2/auth"
DEFAULT_GOOGLE_TOKEN_URI = "https://oauth2.googleapis.com/token"


def create_google_desktop_credentials_file(
    *,
    credentials_path: Path,
    client_id: str,
    client_secret: str,
    project_id: str | None = None,
    auth_uri: str = DEFAULT_GOOGLE_AUTH_URI,
    token_uri: str = DEFAULT_GOOGLE_TOKEN_URI,
) -> None:
    payload = {
        "installed": {
            "client_id": client_id,
            "project_id": project_id or "tutor-assistant",
            "auth_uri": auth_uri,
            "token_uri": token_uri,
            "client_secret": client_secret,
            "redirect_uris": ["http://localhost"],
        }
    }
    credentials_path.write_text(
        json.dumps(payload, ensure_ascii=True, indent=2),
        encoding="utf-8",
    )


def ensure_google_credentials_file(*, credentials_path: Path) -> bool:
    if credentials_path.exists():
        return True

    client_id = os.getenv("GOOGLE_OAUTH_CLIENT_ID", "").strip()
    client_secret = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET", "").strip()
    if not client_id or not client_secret:
        return False

    create_google_desktop_credentials_file(
        credentials_path=credentials_path,
        client_id=client_id,
        client_secret=client_secret,
        project_id=os.getenv("GOOGLE_OAUTH_PROJECT_ID"),
        auth_uri=os.getenv("GOOGLE_OAUTH_AUTH_URI", DEFAULT_GOOGLE_AUTH_URI),
        token_uri=os.getenv("GOOGLE_OAUTH_TOKEN_URI", DEFAULT_GOOGLE_TOKEN_URI),
    )
    return True


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
        if not ensure_google_credentials_file(credentials_path=credentials_path):
            raise FileNotFoundError(
                f"Missing credentials file: {credentials_path}. "
                "Run login_google_user tool or set GOOGLE_OAUTH_CLIENT_ID "
                "and GOOGLE_OAUTH_CLIENT_SECRET."
            )
        flow = InstalledAppFlow.from_client_secrets_file(str(credentials_path), scopes)
        credentials = cast(Credentials, flow.run_local_server(port=0))

    if credentials is None:
        raise RuntimeError(
            "Error obtaining valid Google authentication credentials."
        )

    token_path.write_text(credentials.to_json(), encoding="utf-8")
    return credentials


def _credentials_cover_scopes(
    credentials: Credentials, scopes: tuple[str, ...]
) -> bool:
    return credentials.has_scopes(list(scopes))

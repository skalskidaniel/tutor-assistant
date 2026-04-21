from __future__ import annotations

from datetime import datetime
from pathlib import Path

from googleapiclient.discovery import build

from tutor.core import GOOGLE_ONBOARDING_SCOPES, load_google_credentials, resolve_required_path


def build_drive_service(
    *,
    credentials_path: str | Path | None = "credentials.json",
    token_path: str | Path | None = "token.json",
):
    resolved_credentials_path = resolve_required_path(
        explicit_path=credentials_path,
        env_var_name="GOOGLE_CREDENTIALS_PATH",
    )
    resolved_token_path = resolve_required_path(
        explicit_path=token_path,
        env_var_name="GOOGLE_TOKEN_PATH",
    )
    credentials = load_google_credentials(
        credentials_path=resolved_credentials_path,
        token_path=resolved_token_path,
        scopes=GOOGLE_ONBOARDING_SCOPES,
    )
    return build("drive", "v3", credentials=credentials)


def parse_google_timestamp(value: str) -> datetime:
    if value.endswith("Z"):
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    return datetime.fromisoformat(value)

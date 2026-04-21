import os
from pathlib import Path
from typing import Callable

from tutor_assistant.core import (
    GOOGLE_ONBOARDING_SCOPES,
    create_google_desktop_credentials_file,
    load_google_credentials,
)
from .common import agent_tool, resolve_oauth_value, tool_error_message


def make_login_google_user_tool() -> Callable[..., object]:
    @agent_tool
    def login_google_user(
        client_id: str | None = None,
        client_secret: str | None = None,
        project_id: str | None = None,
        run_browser_auth: bool = True,
    ) -> str:
        """Tworzy credentials.json i opcjonalnie uruchamia logowanie Google uzytkownika."""
        try:
            credentials_path = Path(
                os.getenv("GOOGLE_CREDENTIALS_PATH", "credentials.json")
            )
            token_path = Path(os.getenv("GOOGLE_TOKEN_PATH", "token.json"))

            resolved_client_id = resolve_oauth_value(
                explicit_value=client_id,
                env_var_name="GOOGLE_OAUTH_CLIENT_ID",
            )
            resolved_client_secret = resolve_oauth_value(
                explicit_value=client_secret,
                env_var_name="GOOGLE_OAUTH_CLIENT_SECRET",
            )
            resolved_project_id = resolve_oauth_value(
                explicit_value=project_id,
                env_var_name="GOOGLE_OAUTH_PROJECT_ID",
            )

            if resolved_client_id and resolved_client_secret:
                create_google_desktop_credentials_file(
                    credentials_path=credentials_path,
                    client_id=resolved_client_id,
                    client_secret=resolved_client_secret,
                    project_id=resolved_project_id or None,
                )
            elif not credentials_path.exists():
                raise ValueError(
                    "Brak client_id/client_secret. Podaj je jawnie lub ustaw "
                    "GOOGLE_OAUTH_CLIENT_ID i GOOGLE_OAUTH_CLIENT_SECRET."
                )

            if run_browser_auth:
                load_google_credentials(
                    credentials_path=credentials_path,
                    token_path=token_path,
                    scopes=GOOGLE_ONBOARDING_SCOPES,
                )

            lines = [
                "Logowanie Google przygotowane pomyslnie.",
                f"credentials_path: {credentials_path}",
                f"token_path: {token_path}",
                f"credentials_file_exists: {'tak' if credentials_path.exists() else 'nie'}",
                f"token_file_exists: {'tak' if token_path.exists() else 'nie'}",
            ]
            if run_browser_auth:
                lines.append("OAuth wykonany (przegladarka uruchomiona lokalnie).")
            else:
                lines.append("OAuth pominiety (run_browser_auth=False).")
            return "\n".join(lines)
        except Exception as exc:  # noqa: BLE001
            return tool_error_message(exc)

    return login_google_user

import os
from datetime import datetime
from pathlib import Path
from typing import Callable

from .common import agent_tool
from .models import AgentToolDefaults


def make_get_current_datetime_tool() -> Callable[..., object]:
    @agent_tool
    def get_current_datetime() -> str:
        """Zwraca aktualną lokalną datę, dzień tygodnia i godzinę."""
        now = datetime.now().astimezone()
        weekday_map = {
            0: "poniedzialek",
            1: "wtorek",
            2: "sroda",
            3: "czwartek",
            4: "piatek",
            5: "sobota",
            6: "niedziela",
        }
        weekday_name = weekday_map[now.weekday()]
        return (
            f"Dzisiaj jest {weekday_name}, {now.date().isoformat()}. "
            f"Aktualna godzina: {now.strftime('%H:%M %Z')}."
        )

    return get_current_datetime


def make_get_agent_configuration_tool(
    defaults: AgentToolDefaults,
    default_drive_parent_folder_id: str | None,
    default_homework_db_folder_id: str | None,
) -> Callable[..., object]:
    @agent_tool
    def get_agent_configuration() -> str:
        """Zwraca aktualną konfigurację agenta i dostępów (kalendarz, Google Drive, pliki auth)."""
        credentials_path = Path(
            os.getenv("GOOGLE_CREDENTIALS_PATH", "credentials.json")
        )
        token_path = Path(os.getenv("GOOGLE_TOKEN_PATH", "token.json"))
        lines = [
            "Konfiguracja agenta:",
            f"- calendar_id (domyślnie): {defaults.calendar_id}",
            f"- timezone: {defaults.timezone}",
            f"- drive_parent_folder_id: {default_drive_parent_folder_id or 'brak'}",
            f"- homework_db_folder_id: {default_homework_db_folder_id or 'brak'}",
            f"- google_credentials_path: {credentials_path}",
            f"- credentials_file_exists: {'tak' if credentials_path.exists() else 'nie'}",
            f"- google_token_path: {token_path}",
            f"- token_file_exists: {'tak' if token_path.exists() else 'nie'}",
        ]
        return "\n".join(lines)

    return get_agent_configuration

from typing import Callable

from tutor_assistant.drive_cleanup import DriveCleanupService
from .common import agent_tool, tool_error_message


def make_cleanup_drive_tool(service: DriveCleanupService) -> Callable[..., object]:
    @agent_tool
    def cleanup_drive() -> str:
        """Czysci foldery uczniow na Google Drive (zadania i nazwy notatek)."""
        try:
            result = service.cleanup()

            return (
                "Cleanup Google Drive zakonczony pomyslnie.\n"
                f"Przeskanowani uczniowie: {result.scanned_students}\n"
                f"Usuniete pliki z zadania-domowe: {result.deleted_files}\n"
                f"Zmienione nazwy plikow w notatki: {result.renamed_files}"
            )
        except Exception as exc:  # noqa: BLE001
            return tool_error_message(exc)

    return cleanup_drive

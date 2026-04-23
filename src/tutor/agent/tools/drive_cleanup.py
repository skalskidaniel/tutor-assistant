from typing import Callable

from tutor.drive_cleanup import DriveCleanupService
from .common import agent_tool


def make_cleanup_drive_tool(service: DriveCleanupService) -> Callable[..., object]:
    @agent_tool
    def cleanup_drive() -> str:
        """Czyści foldery uczniów na Google Drive (zadania i nazwy notatek)."""
        result = service.cleanup()

        return (
            "Cleanup Google Drive zakończony pomyślnie.\n"
            f"Przeskanowani uczniowie: {result.scanned_students}\n"
            f"Usunięte pliki z zadania-domowe: {result.deleted_files}\n"
            f"Zmienione nazwy plikow w notatki: {result.renamed_files}"
        )

    return cleanup_drive

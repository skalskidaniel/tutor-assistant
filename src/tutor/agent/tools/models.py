from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class AgentToolDefaults:
    calendar_id: str = "primary"
    timezone: str = "Europe/Warsaw"
    meeting_duration_minutes: int = 60
    drive_parent_folder_id: str | None = None
    homework_db_folder_id: str | None = None
    max_concurrency: int = 4
    progress_callback: Callable[[str], None] | None = None

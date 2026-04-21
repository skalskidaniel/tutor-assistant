from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Literal

@dataclass(frozen=True)
class MeetingSchedule:

    meeting_date: date
    hour: int
    minute: int
    recurrence: Literal["none", "weekly", "biweekly"] = "weekly"
    occurrences: int | None = None

    def __post_init__(self) -> None:
        if self.hour < 0 or self.hour > 23:
            raise ValueError("hour must be in range 0-23.")
        if self.minute < 0 or self.minute > 59:
            raise ValueError("minute must be in range 0-59.")
        if self.occurrences is not None and self.occurrences < 1:
            raise ValueError("occurrences must be positive.")

    @property
    def weekday(self) -> int:
        return self.meeting_date.weekday()

@dataclass(frozen=True)
class WelcomePackage:

    meet_link: str
    drive_folder_url: str
    message_for_student: str

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from tutor.core import slugify


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


class Student(BaseModel):

    model_config = ConfigDict(str_strip_whitespace=True)

    first_name: str = Field(min_length=1)
    last_name: str = Field(min_length=1)
    email: str = Field(min_length=1)
    phone: str = Field(min_length=1)

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"

    @property
    def folder_slug(self) -> str:
        return slugify(f"{self.first_name}-{self.last_name}")


@dataclass(frozen=True)
class WelcomePackage:

    meet_link: str
    drive_folder_url: str
    message_for_student: str

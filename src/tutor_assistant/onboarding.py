"""Onboarding nowego ucznia."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


class NewStudentRequest(BaseModel):
    """Dane potrzebne do przygotowania onboardingu nowego ucznia."""

    model_config = ConfigDict(str_strip_whitespace=True)

    first_name: str = Field(min_length=1)
    last_name: str = Field(min_length=1)
    email: str

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"

    @property
    def folder_slug(self) -> str:
        return slugify(f"{self.first_name}-{self.last_name}")


@dataclass(frozen=True)
class WelcomePackage:
    """Efekt koncowy gotowy do przekazania nauczycielowi."""

    meet_link: str
    drive_folder_url: str
    message_for_student: str


class MeetProvider(Protocol):
    def create_personal_meeting(self, student: NewStudentRequest) -> str:
        """Tworzy spersonalizowany link Google Meet dla ucznia."""
        ...


class DriveProvider(Protocol):
    def create_student_workspace(self, student: NewStudentRequest) -> str:
        """Tworzy strukture katalogow ucznia i zwraca shared_url)."""
        ...


class StudentWelcomeService:
    """Koordynuje pelny onboarding nowego ucznia."""

    def __init__(
        self, meet_provider: MeetProvider, drive_provider: DriveProvider
    ) -> None:
        self._meet_provider = meet_provider
        self._drive_provider = drive_provider

    def onboard_student(self, request: NewStudentRequest) -> WelcomePackage:
        meet_link = self._meet_provider.create_personal_meeting(request)
        drive_folder_url = self._drive_provider.create_student_workspace(request)
        message_for_student = self._build_student_message(
            student=request,
            meet_link=meet_link,
            drive_folder_url=drive_folder_url,
        )

        return WelcomePackage(
            meet_link=meet_link,
            drive_folder_url=drive_folder_url,
            message_for_student=message_for_student,
        )

    @staticmethod
    def _build_student_message(
        student: NewStudentRequest,
        meet_link: str,
        drive_folder_url: str,
    ) -> str:
        return (
            f"Cześć {student.first_name}!\n\n"
            "Witaj w gronie moich uczniów. Ponizej znajdziesz najwazniejsze linki:\n"
            f"- Google Meet: {meet_link}\n"
            f"- Twoj folder na Google Drive: {drive_folder_url}\n\n"
            "W folderze znajdziesz katalogi `zadania-domowe` oraz `notatki`. "
            "Do zobaczenia na pierwszych zajeciach!"
        )


class InMemoryMeetProvider:
    """Prosta implementacja testowa - bez polaczenia z Google API."""

    def create_personal_meeting(self, student: NewStudentRequest) -> str:
        token = f"{student.folder_slug}-{uuid4().hex[:8]}"
        return f"https://meet.google.com/{token}"


class InMemoryDriveProvider:
    """Prosta implementacja testowa - zwraca docelowa strukture katalogow."""

    def create_student_workspace(self, student: NewStudentRequest) -> tuple[str, str]:
        root = student.folder_slug
        structure = (
            f"{root}/\n"
            "|-- zadania-domowe/\n"
            "|   |-- funkcja-kwadratowa.pdf\n"
            "|   `-- wielomiany.pdf\n"
            "`-- notatki/\n"
            "    |-- funkcja-kwadratowa.pdf\n"
            "    |-- planimetria.pdf\n"
            "    |-- geometria-analityczna.pdf\n"
            "    `-- wzory-viete.pdf"
        )
        shared_url = f"https://drive.google.com/drive/folders/{root}-{uuid4().hex[:10]}"
        return structure, shared_url


def slugify(value: str) -> str:
    normalized = value.lower().strip()
    normalized = normalized.replace("ą", "a")
    normalized = normalized.replace("ć", "c")
    normalized = normalized.replace("ę", "e")
    normalized = normalized.replace("ł", "l")
    normalized = normalized.replace("ń", "n")
    normalized = normalized.replace("ó", "o")
    normalized = normalized.replace("ś", "s")
    normalized = normalized.replace("ź", "z")
    normalized = normalized.replace("ż", "z")

    result: list[str] = []
    previous_dash = False
    for char in normalized:
        if char.isalnum():
            result.append(char)
            previous_dash = False
        elif not previous_dash:
            result.append("-")
            previous_dash = True

    slug = "".join(result).strip("-")
    return slug or "uczen"

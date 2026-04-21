"""Application service for onboarding flow."""

from __future__ import annotations

from .models import Student, WelcomePackage, MeetingSchedule
from .providers import DriveProvider, MeetProvider


class StudentWelcomeService:
    """Koordynuje pelny onboarding nowego ucznia."""

    def __init__(
        self, meet_provider: MeetProvider, drive_provider: DriveProvider
    ) -> None:
        self._meet_provider = meet_provider
        self._drive_provider = drive_provider

    def onboard_student(
        self, request: Student, schedule: MeetingSchedule
    ) -> WelcomePackage:
        meet_link = self._meet_provider.create_personal_meeting(request, schedule)
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
        student: Student,
        meet_link: str,
        drive_folder_url: str,
    ) -> str:
        return (
            f"Czesc {student.first_name}!\n\n"
            "Witaj w gronie moich uczniow. Ponizej znajdziesz najwazniejsze linki:\n"
            f"- Google Meet: {meet_link}\n"
            f"- Twoj folder na Google Drive: {drive_folder_url}\n"
            "W folderze znajdziesz katalogi `zadania-domowe` oraz `notatki`. "
            "Do zobaczenia na pierwszych zajeciach!"
        )

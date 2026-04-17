"""CLI do uruchomienia onboardingu nowego ucznia (Use Case 2)."""

from __future__ import annotations

import argparse
from datetime import date

from tutor_assistant.onboarding import (
    GoogleDriveProvider,
    GoogleMeetProvider,
    MeetingSchedule,
    NewStudentRequest,
    StudentWelcomeService,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Tworzy link Google Meet i folder Google Drive dla nowego ucznia."
    )
    parser.add_argument("--first-name", required=True, help="Imie ucznia")
    parser.add_argument("--last-name", required=True, help="Nazwisko ucznia")
    parser.add_argument("--email", required=True, help="Email ucznia")
    parser.add_argument("--phone", required=True, help="Telefon ucznia")
    parser.add_argument(
        "--calendar-id",
        default="primary",
        help="ID kalendarza Google (domyslnie: primary)",
    )
    parser.add_argument(
        "--meeting-duration-minutes",
        type=int,
        default=60,
        help="Dlugosc spotkania onboardingowego (domyslnie: 60)",
    )
    parser.add_argument(
        "--timezone",
        default="Europe/Warsaw",
        help="Strefa czasowa dla wydarzenia (domyslnie: Europe/Warsaw)",
    )
    parser.add_argument(
        "--drive-parent-folder-id",
        default=None,
        help="Opcjonalny folder nadrzedny na Google Drive",
    )
    parser.add_argument(
        "--meeting-date", required=True, help="Data pierwszego spotkania YYYY-MM-DD"
    )
    parser.add_argument(
        "--hour",
        type=int,
        required=True,
        help="Godzina spotkania 0-23",
    )
    parser.add_argument(
        "--minute",
        type=int,
        required=True,
        help="Minuta spotkania 0-59",
    )
    parser.add_argument(
        "--recurrence",
        choices=("none", "weekly", "biweekly"),
        default="weekly",
        help="Powtarzalnosc spotkania (domyslnie: weekly)",
    )
    parser.add_argument(
        "--occurrences",
        type=int,
        default=None,
        help="Opcjonalna liczba wystapien spotkania",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()

    request = NewStudentRequest(
        first_name=args.first_name,
        last_name=args.last_name,
        email=args.email,
        phone=args.phone,
    )
    meeting_date = date.fromisoformat(args.meeting_date)
    schedule = MeetingSchedule(
        meeting_date=meeting_date,
        hour=args.hour,
        minute=args.minute,
        recurrence=args.recurrence,
        occurrences=args.occurrences,
    )

    meet_provider = GoogleMeetProvider(
        calendar_id=args.calendar_id,
        timezone=args.timezone,
        meeting_duration_minutes=args.meeting_duration_minutes,
        schedule=schedule,
    )
    drive_provider = GoogleDriveProvider(parent_folder_id=args.drive_parent_folder_id)

    service = StudentWelcomeService(
        meet_provider=meet_provider,
        drive_provider=drive_provider,
    )
    package = service.onboard_student(request)

    print("Onboarding zakonczony pomyslnie.\n")
    print(f"Google Meet: {package.meet_link}")
    print(f"Google Drive: {package.drive_folder_url}\n")
    print("Wiadomosc do ucznia:")
    print("-" * 40)
    print(package.message_for_student)


if __name__ == "__main__":
    main()

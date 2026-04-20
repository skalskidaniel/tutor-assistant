"""CLI dla use case'ow asystenta nauczyciela."""

from __future__ import annotations

import argparse
from datetime import date, datetime
import os
from pathlib import Path

from dotenv import load_dotenv

from tutor_assistant.daily_summary import (
    BedrockLessonInsightsProvider,
    DailySummaryService,
    GoogleDriveStudentNotesProvider,
    PyMuPdfRecentPagesProvider,
)
from tutor_assistant.drive_cleanup import (
    DriveCleanupService,
    GoogleDriveCleanupProvider,
)
from tutor_assistant.homework import (
    BedrockHomeworkMatcher,
    GoogleDriveHomeworkProvider,
    HomeworkService,
)
from tutor_assistant.core import GoogleCalendarLessonProvider
from tutor_assistant.onboarding import (
    GoogleDriveProvider,
    GoogleMeetProvider,
    MeetingSchedule,
    NewStudentRequest,
    StudentWelcomeService,
)
from tutor_assistant.vacation import (
    GmailProvider,
    VacationNotificationService,
    VacationRequest,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Uruchamia workflow use case'ow asystenta nauczyciela."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    onboard = subparsers.add_parser(
        "onboard",
        help="Use Case 2: onboarding nowego ucznia",
    )
    onboard.add_argument("--first-name", required=True, help="Imie ucznia")
    onboard.add_argument("--last-name", required=True, help="Nazwisko ucznia")
    onboard.add_argument("--email", required=True, help="Email ucznia")
    onboard.add_argument("--phone", required=True, help="Telefon ucznia")
    onboard.add_argument(
        "--calendar-id",
        default="primary",
        help="ID kalendarza Google (domyslnie: primary)",
    )
    onboard.add_argument(
        "--meeting-duration-minutes",
        type=int,
        default=60,
        help="Dlugosc spotkania onboardingowego (domyslnie: 60)",
    )
    onboard.add_argument(
        "--timezone",
        default="Europe/Warsaw",
        help="Strefa czasowa dla wydarzenia (domyslnie: Europe/Warsaw)",
    )
    onboard.add_argument(
        "--drive-parent-folder-id",
        default=None,
        help="Opcjonalny folder nadrzedny na Google Drive",
    )
    onboard.add_argument(
        "--meeting-date", required=True, help="Data pierwszego spotkania YYYY-MM-DD"
    )
    onboard.add_argument(
        "--hour",
        type=int,
        required=True,
        help="Godzina spotkania 0-23",
    )
    onboard.add_argument(
        "--minute",
        type=int,
        required=True,
        help="Minuta spotkania 0-59",
    )
    onboard.add_argument(
        "--recurrence",
        choices=("none", "weekly", "biweekly"),
        default="weekly",
        help="Powtarzalnosc spotkania (domyslnie: weekly)",
    )
    onboard.add_argument(
        "--occurrences",
        type=int,
        default=None,
        help="Opcjonalna liczba wystapien spotkania",
    )

    cleanup = subparsers.add_parser(
        "cleanup-drive",
        help="Use Case 4: cleanup folderow Google Drive",
    )
    cleanup.add_argument(
        "--drive-parent-folder-id",
        default=None,
        help="Folder nadrzedny, zawierajacy foldery uczniow",
    )

    vacation = subparsers.add_parser(
        "vacation",
        help="Use Case 3: powiadomienia o nieobecnosci",
    )
    vacation.add_argument("--start-date", required=True, help="Data startu YYYY-MM-DD")
    vacation.add_argument(
        "--end-date",
        default=None,
        help="Data konca YYYY-MM-DD (domyslnie taka sama jak start-date)",
    )
    vacation.add_argument(
        "--calendar-id",
        default="primary",
        help="ID kalendarza Google (domyslnie: primary)",
    )
    vacation.add_argument(
        "--send-emails",
        action="store_true",
        help="Wyslij automatycznie e-maile do uczniow",
    )

    daily_summary = subparsers.add_parser(
        "daily-summary",
        help="Use Case 1: dzienne podsumowanie zajec",
    )
    daily_summary.add_argument(
        "--date",
        default=None,
        help="Data podsumowania YYYY-MM-DD (domyslnie dzisiaj)",
    )
    daily_summary.add_argument(
        "--calendar-id",
        default="primary",
        help="ID kalendarza Google (domyslnie: primary)",
    )
    daily_summary.add_argument(
        "--drive-parent-folder-id",
        default=None,
        help="Folder nadrzedny, zawierajacy foldery uczniow",
    )
    daily_summary.add_argument(
        "--max-concurrency",
        type=int,
        default=4,
        help="Maksymalna liczba rownoleglych analiz lekcji (domyslnie: 4)",
    )

    upload_homework = subparsers.add_parser(
        "upload-homework",
        help="Use Case 5: upload zadan domowych po lekcjach",
    )
    upload_homework.add_argument(
        "--date",
        default=None,
        help="Data zajec YYYY-MM-DD (domyslnie dzisiaj)",
    )
    upload_homework.add_argument(
        "--calendar-id",
        default="primary",
        help="ID kalendarza Google (domyslnie: primary)",
    )
    upload_homework.add_argument(
        "--drive-parent-folder-id",
        default=None,
        help="Folder nadrzedny, zawierajacy foldery uczniow",
    )
    upload_homework.add_argument(
        "--homework-db-folder-id",
        default=None,
        help="Folder bazy zadan domowych na Google Drive",
    )
    upload_homework.add_argument(
        "--max-concurrency",
        type=int,
        default=4,
        help="Maksymalna liczba rownoleglych uploadow (domyslnie: 4)",
    )

    return parser


def main() -> None:
    load_dotenv(Path(".env"), override=True)
    args = build_parser().parse_args()

    if args.command == "onboard":
        _run_onboard(args)
        return

    if args.command == "cleanup-drive":
        _run_cleanup_drive(args)
        return

    if args.command == "vacation":
        _run_vacation(args)
        return

    if args.command == "daily-summary":
        _run_daily_summary(args)
        return

    if args.command == "upload-homework":
        _run_upload_homework(args)
        return

    raise RuntimeError(f"Nieznana komenda CLI: {args.command}")


def _run_onboard(args: argparse.Namespace) -> None:

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


def _run_cleanup_drive(args: argparse.Namespace) -> None:
    provider = GoogleDriveCleanupProvider(parent_folder_id=args.drive_parent_folder_id)
    service = DriveCleanupService(provider=provider)
    result = service.cleanup()

    print("Cleanup Google Drive zakonczony pomyslnie.\n")
    print(f"Przeskanowani uczniowie: {result.scanned_students}")
    print(f"Usuniete pliki z zadania-domowe: {result.deleted_files}")
    print(f"Zmienione nazwy plikow w notatki: {result.renamed_files}")


def _run_vacation(args: argparse.Namespace) -> None:
    start_date = date.fromisoformat(args.start_date)
    end_date = date.fromisoformat(args.end_date) if args.end_date else start_date
    request = VacationRequest(start_date=start_date, end_date=end_date)

    calendar_provider = GoogleCalendarLessonProvider(calendar_id=args.calendar_id)
    email_provider = GmailProvider() if args.send_emails else None
    service = VacationNotificationService(
        calendar_provider=calendar_provider,
        email_provider=email_provider,
    )
    result = service.prepare_notifications(
        request=request,
        send_emails=args.send_emails,
    )

    print("Powiadomienia o nieobecnosci przygotowane.\n")
    print(f"Przeskanowane wydarzenia: {result.scanned_events}")
    print(f"Liczba uczniow do powiadomienia: {len(result.notices)}\n")

    for index, notice in enumerate(result.notices, start=1):
        print(f"[{index}] Uczen: {notice.student_name}")
        print(f"Telefon: {notice.student_phone or 'brak'}")
        print(f"Email: {notice.student_email or 'brak'}")
        print("Wiadomosc:")
        print(notice.message)
        if args.send_emails:
            status = "wyslany" if notice.email_sent else "pominiety (brak e-maila)"
            print(f"Status e-maila: {status}")
        print("-" * 40)


def _run_daily_summary(args: argparse.Namespace) -> None:
    target_date = date.fromisoformat(args.date) if args.date else date.today()
    selected_parent_folder_id = args.drive_parent_folder_id or os.getenv(
        "GOOGLE_DRIVE_PARENT_FOLDER_ID"
    )

    calendar_provider = GoogleCalendarLessonProvider(
        calendar_id=args.calendar_id,
        include_drive_scope=True,
    )
    notes_provider = GoogleDriveStudentNotesProvider(
        parent_folder_id=selected_parent_folder_id
    )
    pdf_recent_pages_provider = PyMuPdfRecentPagesProvider(recent_pages_count=3)
    insights_provider = BedrockLessonInsightsProvider()

    service = DailySummaryService(
        calendar_provider=calendar_provider,
        notes_provider=notes_provider,
        pdf_recent_pages_provider=pdf_recent_pages_provider,
        insights_provider=insights_provider,
        max_concurrency=args.max_concurrency,
    )
    result = service.build_summary_for_day(target_date=target_date)

    print(f"Dzienne podsumowanie zajec dla: {target_date.isoformat()}\n")
    print(f"Liczba zaplanowanych lekcji: {result.scanned_events}")
    print(f"Liczba podsumowan: {len(result.lesson_summaries)}\n")

    if result.lesson_summaries and all(
        lesson.source_pdf_name is None for lesson in result.lesson_summaries
    ):
        print(
            "Uwaga: nie znaleziono zadnych notatek PDF. "
            "Sprawdz GOOGLE_DRIVE_PARENT_FOLDER_ID lub --drive-parent-folder-id."
        )
        print(f"Aktualny folder nadrzedny: {selected_parent_folder_id or 'brak'}\n")

    for index, lesson in enumerate(result.lesson_summaries, start=1):
        lesson_time = _format_lesson_time_range(
            start=lesson.lesson_start_time,
            end=lesson.lesson_end_time,
        )
        print(f"[{index}] Godzina: {lesson_time}")
        print(f"Uczen: {lesson.student_name}")
        print(f"Notatki PDF: {lesson.source_pdf_name or 'brak'}")
        print("Ostatnie notatki (na podstawie 3 ostatnich stron):")
        print(lesson.recent_notes_summary)
        print("-" * 40)


def _run_upload_homework(args: argparse.Namespace) -> None:
    target_date = date.fromisoformat(args.date) if args.date else date.today()
    selected_parent_folder_id = args.drive_parent_folder_id or os.getenv(
        "GOOGLE_DRIVE_PARENT_FOLDER_ID"
    )
    selected_homework_db_folder_id = args.homework_db_folder_id or os.getenv(
        "GOOGLE_HOMEWORK_DATABASE_FOLDER_ID"
    )

    calendar_provider = GoogleCalendarLessonProvider(
        calendar_id=args.calendar_id,
        include_drive_scope=True,
    )
    notes_provider = GoogleDriveStudentNotesProvider(
        parent_folder_id=selected_parent_folder_id
    )
    pdf_recent_pages_provider = PyMuPdfRecentPagesProvider(recent_pages_count=3)
    insights_provider = BedrockLessonInsightsProvider()
    homework_drive_provider = GoogleDriveHomeworkProvider(
        parent_folder_id=selected_parent_folder_id,
        homework_database_folder_id=selected_homework_db_folder_id,
    )
    homework_matcher = BedrockHomeworkMatcher()

    service = HomeworkService(
        calendar_provider=calendar_provider,
        notes_provider=notes_provider,
        pdf_recent_pages_provider=pdf_recent_pages_provider,
        insights_provider=insights_provider,
        homework_drive_provider=homework_drive_provider,
        homework_matcher=homework_matcher,
        max_concurrency=args.max_concurrency,
    )
    result = service.upload_homework_for_day(target_date=target_date)

    print(f"Upload zadan domowych dla: {target_date.isoformat()}\n")
    print(f"Liczba zaplanowanych lekcji: {result.scanned_events}")
    print(f"Liczba przeslanych zadan: {result.uploaded_homeworks}\n")

    for index, assignment in enumerate(result.assignments, start=1):
        lesson_time = _format_lesson_time_range(
            start=assignment.lesson_start_time,
            end=assignment.lesson_end_time,
        )
        print(f"[{index}] Godzina: {lesson_time}")
        print(f"Uczen: {assignment.student_name}")
        print(f"Szczegoly: {assignment.status_details}")
        print(f"Wgrane zadanie: {assignment.uploaded_homework_name or 'brak'}")
        print("-" * 40)


def _format_lesson_time_range(
    *,
    start: datetime | None,
    end: datetime | None,
) -> str:
    if start is None:
        return "brak"

    start_label = _format_clock_time(start)
    if end is None:
        return start_label

    end_label = _format_clock_time(end)
    return f"{start_label}-{end_label}"


def _format_clock_time(value: datetime) -> str:
    if value.tzinfo is None:
        return value.strftime("%H:%M")
    return value.astimezone().strftime("%H:%M")


if __name__ == "__main__":
    main()

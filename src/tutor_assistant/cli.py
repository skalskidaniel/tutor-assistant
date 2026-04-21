"""CLI dla use case'ow asystenta nauczyciela."""

from __future__ import annotations

import argparse
from datetime import date, datetime
import os
from pathlib import Path

from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from tutor_assistant.agent import (
    AgentToolDefaults,
    build_chat_session,
    resolve_agent_model_id,
)
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
from tutor_assistant.core.memory import DEFAULT_MEMORY_NAMESPACE, MemoryService
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

    chat = subparsers.add_parser(
        "chat",
        help="Tryb interaktywnego agenta (Strands + Bedrock)",
    )
    chat.add_argument(
        "--calendar-id",
        default="primary",
        help="ID kalendarza Google (domyslnie: primary)",
    )
    chat.add_argument(
        "--timezone",
        default="Europe/Warsaw",
        help="Strefa czasowa spotkan onboardingowych (domyslnie: Europe/Warsaw)",
    )
    chat.add_argument(
        "--meeting-duration-minutes",
        type=int,
        default=60,
        help="Dlugosc spotkania onboardingowego (domyslnie: 60)",
    )
    chat.add_argument(
        "--drive-parent-folder-id",
        default=None,
        help="Folder nadrzedny, zawierajacy foldery uczniow",
    )
    chat.add_argument(
        "--homework-db-folder-id",
        default=None,
        help="Folder bazy zadan domowych na Google Drive",
    )
    chat.add_argument(
        "--max-concurrency",
        type=int,
        default=4,
        help="Maksymalna liczba rownoleglych analiz/uploadow (domyslnie: 4)",
    )
    chat.add_argument(
        "--thread-id",
        default="teacher-cli",
        help="Identyfikator sesji konwersacji (domyslnie: teacher-cli)",
    )
    chat.add_argument(
        "--hide-tools",
        action="store_true",
        help="Ukryj logi wywolan narzedzi w trakcie odpowiedzi agenta",
    )
    chat.add_argument(
        "--show-reasoning",
        action="store_true",
        help="Pokaz krotkie logi procesu pracy agenta",
    )

    memory_set = subparsers.add_parser(
        "memory-set",
        help="Zapisuje trwala wartosc w pamieci agenta",
    )
    memory_set.add_argument("--key", required=True, help="Klucz pamieci")
    memory_set.add_argument("--value", required=True, help="Wartosc do zapisania")
    memory_set.add_argument(
        "--thread-id",
        default=DEFAULT_MEMORY_NAMESPACE,
        help="Namespace pamieci (domyslnie: teacher-cli)",
    )

    memory_list = subparsers.add_parser(
        "memory-list",
        help="Wyswietla zapisana pamiec agenta",
    )
    memory_list.add_argument(
        "--thread-id",
        default=DEFAULT_MEMORY_NAMESPACE,
        help="Namespace pamieci (domyslnie: teacher-cli)",
    )

    memory_delete = subparsers.add_parser(
        "memory-delete",
        help="Usuwa klucz z pamieci agenta",
    )
    memory_delete.add_argument("--key", required=True, help="Klucz pamieci")
    memory_delete.add_argument(
        "--thread-id",
        default=DEFAULT_MEMORY_NAMESPACE,
        help="Namespace pamieci (domyslnie: teacher-cli)",
    )

    return parser


def main() -> None:
    load_dotenv(Path(".env"), override=True)
    _configure_langsmith_env_aliases()
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

    if args.command == "chat":
        _run_chat(args)
        return

    if args.command == "memory-set":
        _run_memory_set(args)
        return

    if args.command == "memory-list":
        _run_memory_list(args)
        return

    if args.command == "memory-delete":
        _run_memory_delete(args)
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


def _run_chat(args: argparse.Namespace) -> None:
    console = Console()
    status = console.status("[bold green]Agent mysli...[/bold green]", spinner="dots")

    defaults = AgentToolDefaults(
        calendar_id=args.calendar_id,
        timezone=args.timezone,
        meeting_duration_minutes=args.meeting_duration_minutes,
        drive_parent_folder_id=args.drive_parent_folder_id,
        homework_db_folder_id=args.homework_db_folder_id,
        max_concurrency=args.max_concurrency,
        progress_callback=status.update,
    )
    session = build_chat_session(defaults=defaults, thread_id=args.thread_id)
    show_tools = not args.hide_tools
    show_reasoning = args.show_reasoning
    model_id = resolve_agent_model_id()

    _print_chat_header(console, model_id)

    while True:
        try:
            user_input = console.input("[bold white]>[/bold white] ").strip()
        except EOFError:
            console.print("\nKoniec danych wejsciowych. Zamykam sesje.")
            return
        except KeyboardInterrupt:
            console.print("\nPrzerwano. Zamykam sesje.")
            return

        if not user_input:
            continue

        if user_input.casefold() in {"exit", "quit"}:
            console.print("Do uslyszenia!")
            return

        status.update("[bold green]Agent mysli...[/bold green]")
        status.start()
        status_running = True
        started_response = False

        try:
            for event in session.stream(user_input):
                if event.kind == "tool":
                    if show_tools:
                        if event.status == "pending":
                            status.update(f"[grey50]{event.text}...[/grey50]")
                            if not status_running:
                                status.start()
                                status_running = True
                        else:
                            if status_running:
                                status.update("[bold green]Agent mysli...[/bold green]")
                            if started_response:
                                console.print()
                                started_response = False
                            _print_tool_event(
                                console, event.text, event.status, event.summary
                            )
                    continue

                if not started_response:
                    if status_running:
                        status.stop()
                        status_running = False
                    console.print("[bold #e27d60]Agent>[/bold #e27d60] ", end="")
                    started_response = True

                # Check for tool output tags and strip them
                output_text = event.text
                if event.kind == "tool_output":
                    output_text = (
                        output_text.replace("<tool_output>\n", "")
                        .replace("\n</tool_output>\n", "")
                        .replace("<tool_output>", "")
                        .replace("</tool_output>", "")
                    )

                console.print(
                    output_text,
                    end="",
                    highlight=False,
                    markup=False,
                )
        except Exception as exc:  # noqa: BLE001
            if status_running:
                status.stop()
                status_running = False
            console.print(f"[red]Blad agenta:[/red] {exc}\n")
            continue

        if status_running:
            status.stop()
            status_running = False

        if started_response:
            console.print()
            console.print()
            continue

        if show_reasoning:
            console.print("[dim]Agent zakonczyl zadanie bez tresci odpowiedzi.[/dim]")
        console.print("[bold #e27d60]Agent>[/bold #e27d60] Gotowe.\n")


def _run_memory_set(args: argparse.Namespace) -> None:
    memory_service = MemoryService()
    memory_service.set(namespace=args.thread_id, key=args.key, value=args.value)

    print("Zapisano wartosc w pamieci agenta.\n")
    print(f"thread_id: {args.thread_id}")
    print(f"key: {args.key}")


def _run_memory_list(args: argparse.Namespace) -> None:
    memory_service = MemoryService()
    entries = memory_service.get_all(namespace=args.thread_id)

    print(f"Pamiec agenta dla thread_id={args.thread_id}:\n")
    if not entries:
        print("(pusto)")
        return

    for key in sorted(entries):
        print(f"- {key}: {entries[key]}")


def _run_memory_delete(args: argparse.Namespace) -> None:
    memory_service = MemoryService()
    deleted = memory_service.delete(namespace=args.thread_id, key=args.key)

    print(f"thread_id: {args.thread_id}")
    print(f"key: {args.key}")
    if deleted:
        print("Status: usunieto")
    else:
        print("Status: brak klucza")


def _print_chat_header(console: Console, model_id: str) -> None:
    icon = Text.assemble(
        ("   ▄▄██▄▄   \n", "bold #5bc0de"),
        (" ▄█ ▀  ▀ █▄ \n", "bold #5bc0de"),
        ("  ▀▀▄▄▄▄▀▀  ", "bold #5bc0de"),
    )

    meta = Text()
    meta.append("Tutor assistant\n", style="bold white")
    meta.append(f"Model: {model_id}", style="grey70")

    grid = Table.grid(padding=(0, 2))
    grid.add_column(no_wrap=True)
    grid.add_column()
    grid.add_row(icon, meta)

    header = Panel(
        grid,
        border_style="grey23",
        padding=(1, 2),
        expand=False,
    )
    console.print(header)


def _print_tool_event(
    console: Console,
    tool_name: str,
    status: str | None,
    summary: str | None,
) -> None:
    if status == "completed":
        style = "green"
        marker = "[done]"
    elif status == "error":
        style = "red"
        marker = "[error]"
    else:
        style = "grey50"
        marker = "[tool]"

    text = Text()
    text.append(f"{marker} ", style=style)
    text.append(tool_name, style=style)
    # Odkomentuj ponizsze linie jesli kiedys bedziesz chcial dodac summary do logow narzedzi
    # if summary:
    #     text.append(f" - {summary}", style="grey66")

    console.print(text)
    # Zostawiamy print bez nowej linii na koncu, aby wywietlanie narzedzi bylo bardziej zwarte


def _configure_langsmith_env_aliases() -> None:
    alias_map = {
        "LANGCHAIN_TRACING_V2": "LANGSMITH_TRACING",
        "LANGCHAIN_API_KEY": "LANGSMITH_API_KEY",
        "LANGCHAIN_PROJECT": "LANGSMITH_PROJECT",
        "LANGCHAIN_ENDPOINT": "LANGSMITH_ENDPOINT",
    }

    for langchain_var, langsmith_var in alias_map.items():
        if os.getenv(langchain_var):
            continue

        langsmith_value = os.getenv(langsmith_var)
        if langsmith_value:
            os.environ[langchain_var] = langsmith_value


def _is_truthy_env(value: str) -> bool:
    return value.strip().casefold() in {"1", "true", "yes", "on"}


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

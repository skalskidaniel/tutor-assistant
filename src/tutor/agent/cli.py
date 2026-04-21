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

from tutor.agent import (
    AgentToolDefaults,
    build_chat_session,
    resolve_agent_model_id,
    ThinkingStreamState,
)
from tutor.daily_summary import (
    BedrockLessonInsightsProvider,
    DailySummaryService,
    GoogleDriveStudentNotesProvider,
    PyMuPdfRecentPagesProvider,
)
from tutor.drive_cleanup import (
    DriveCleanupService,
    GoogleDriveCleanupProvider,
)
from tutor.homework import (
    BedrockHomeworkMatcher,
    GoogleDriveHomeworkProvider,
    HomeworkService,
)
from tutor.core import GoogleCalendarLessonProvider
from tutor.core import Student
from tutor.core.memory import DEFAULT_MEMORY_NAMESPACE, MemoryService
from tutor.onboarding import (
    GoogleDriveProvider,
    GoogleMeetProvider,
    MeetingSchedule,
    StudentWelcomeService,
)
from tutor.vacation import (
    GmailProvider,
    VacationNotificationService,
    VacationRequest,
)

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Uruchamia workflow use case'ów asystenta nauczyciela."
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
        help="ID kalendarza Google (domyślnie: primary)",
    )
    onboard.add_argument(
        "--meeting-duration-minutes",
        type=int,
        default=60,
        help="Długość spotkania (domyślnie: 60)",
    )
    onboard.add_argument(
        "--timezone",
        default="Europe/Warsaw",
        help="Strefa czasowa dla wydarzenia (domyślnie: Europe/Warsaw)",
    )
    onboard.add_argument(
        "--drive-parent-folder-id",
        default=os.getenv("GOOGLE_DRIVE_PARENT_FOLDER_ID"),
        help="Opcjonalny folder nadrzędny na Google Drive",
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
        help="Powtarzalność spotkania (domyślnie: weekly)",
    )
    onboard.add_argument(
        "--occurrences",
        type=int,
        default=None,
        help="Opcjonalna liczba wystąpień spotkania",
    )

    cleanup = subparsers.add_parser(
        "cleanup-drive",
        help="Use Case 4: cleanup folderów Google Drive",
    )
    cleanup.add_argument(
        "--drive-parent-folder-id",
        default=None,
        help="Folder nadrzędny, zawierający foldery uczniów",
    )

    vacation = subparsers.add_parser(
        "vacation",
        help="Use Case 3: powiadomienia o nieobecności",
    )
    vacation.add_argument("--start-date", required=True, help="Data startu YYYY-MM-DD")
    vacation.add_argument(
        "--end-date",
        default=None,
        help="Data końca YYYY-MM-DD (domyślnie taka sama jak start-date)",
    )
    vacation.add_argument(
        "--calendar-id",
        default="primary",
        help="ID kalendarza Google (domyślnie: primary)",
    )
    vacation.add_argument(
        "--send-emails",
        action="store_true",
        help="Wyślij automatycznie e-maile do uczniów",
    )

    daily_summary = subparsers.add_parser(
        "daily-summary",
        help="Use Case 1: dzienne podsumowanie zajęć",
    )
    daily_summary.add_argument(
        "--date",
        default=None,
        help="Data podsumowania YYYY-MM-DD (domyślnie dzisiaj)",
    )
    daily_summary.add_argument(
        "--calendar-id",
        default="primary",
        help="ID kalendarza Google (domyślnie: primary)",
    )
    daily_summary.add_argument(
        "--drive-parent-folder-id",
        default=None,
        help="Folder nadrzędny, zawierający foldery uczniów",
    )
    daily_summary.add_argument(
        "--max-concurrency",
        type=int,
        default=4,
        help="Maksymalna liczba równoległych analiz lekcji (domyślnie: 4)",
    )

    upload_homework = subparsers.add_parser(
        "upload-homework",
        help="Use Case 5: upload zadań domowych po lekcjach",
    )
    upload_homework.add_argument(
        "--date",
        default=None,
        help="Data zajęć YYYY-MM-DD (domyślnie dzisiaj)",
    )
    upload_homework.add_argument(
        "--calendar-id",
        default="primary",
        help="ID kalendarza Google (domyślnie: primary)",
    )
    upload_homework.add_argument(
        "--drive-parent-folder-id",
        default=None,
        help="Folder nadrzędny, zawierający foldery uczniów",
    )
    upload_homework.add_argument(
        "--homework-db-folder-id",
        default=None,
        help="Folder bazy zadań domowych na Google Drive",
    )
    upload_homework.add_argument(
        "--max-concurrency",
        type=int,
        default=4,
        help="Maksymalna liczba równoległych uploadów (domyślnie: 4)",
    )

    chat = subparsers.add_parser(
        "chat",
        help="Tryb interaktywnego agenta",
    )
    chat.add_argument(
        "--calendar-id",
        default="primary",
        help="ID kalendarza Google (domyślnie: primary)",
    )
    chat.add_argument(
        "--timezone",
        default="Europe/Warsaw",
        help="Strefa czasowa spotkań (domyślnie: Europe/Warsaw)",
    )
    chat.add_argument(
        "--meeting-duration-minutes",
        type=int,
        default=60,
        help="Dlugość spotkania (domyślnie: 60)",
    )
    chat.add_argument(
        "--drive-parent-folder-id",
        default=None,
        help="Folder nadrzędny, zawierający foldery uczniów",
    )
    chat.add_argument(
        "--homework-db-folder-id",
        default=None,
        help="Folder bazy zadań domowych na Google Drive",
    )
    chat.add_argument(
        "--max-concurrency",
        type=int,
        default=4,
        help="Maksymalna liczba równoległych analiz/uploadow (domyślnie: 4)",
    )
    chat.add_argument(
        "--thread-id",
        default="teacher-cli",
        help="Identyfikator sesji konwersacji (domyślnie: teacher-cli)",
    )
    chat.add_argument(
        "--hide-tools",
        action="store_true",
        help="Ukryj logi wywołań narzędzi w trakcie odpowiedzi agenta",
    )
    chat.add_argument(
        "--show-reasoning",
        action="store_true",
        help="Pokaz krótkie logi procesu pracy agenta",
    )

    memory_set = subparsers.add_parser(
        "memory-set",
        help="Zapisuje trwałą wartość w pamięci agenta",
    )
    memory_set.add_argument("--key", required=True, help="Klucz pamięci")
    memory_set.add_argument("--value", required=True, help="Wartość do zapisania")
    memory_set.add_argument(
        "--thread-id",
        default=DEFAULT_MEMORY_NAMESPACE,
        help="Namespace pamięci (domyślnie: teacher-cli)",
    )

    memory_list = subparsers.add_parser(
        "memory-list",
        help="Wyświetla zapisaną pamięć agenta",
    )
    memory_list.add_argument(
        "--thread-id",
        default=DEFAULT_MEMORY_NAMESPACE,
        help="Namespace pamięci (domyślnie: teacher-cli)",
    )

    memory_delete = subparsers.add_parser(
        "memory-delete",
        help="Usuwa klucz z pamięci agenta",
    )
    memory_delete.add_argument("--key", required=True, help="Klucz pamięci")
    memory_delete.add_argument(
        "--thread-id",
        default=DEFAULT_MEMORY_NAMESPACE,
        help="Namespace pamięci (domyślnie: teacher-cli)",
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

    request = Student(
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
    )
    drive_provider = GoogleDriveProvider(parent_folder_id=args.drive_parent_folder_id)

    service = StudentWelcomeService(
        meet_provider=meet_provider,
        drive_provider=drive_provider,
    )
    package = service.onboard_student(request, schedule)

    print("Onboarding zakończony pomyślnie.\n")
    print(f"Google Meet: {package.meet_link}")
    print(f"Google Drive: {package.drive_folder_url}\n")
    print("Wiadomość do ucznia:")
    print("-" * 40)
    print(package.message_for_student)


def _run_cleanup_drive(args: argparse.Namespace) -> None:
    provider = GoogleDriveCleanupProvider(student_notes_folder_id=args.drive_parent_folder_id)
    service = DriveCleanupService(provider=provider)
    result = service.cleanup()

    print("Cleanup Google Drive zakończony pomyślnie.\n")
    print(f"Przeskanowani uczniowie: {result.scanned_students}")
    print(f"Usunięte pliki z zadania-domowe: {result.deleted_files}")
    print(f"Zmienione nazwy plików w notatki: {result.renamed_files}")


def _run_vacation(args: argparse.Namespace) -> None:
    start_date = date.fromisoformat(args.start_date)
    end_date = date.fromisoformat(args.end_date) if args.end_date else start_date
    request = VacationRequest(start_date=start_date, end_date=end_date)

    calendar_provider = GoogleCalendarLessonProvider(calendar_id=args.calendar_id)
    email_provider = GmailProvider() if args.send_emails else None
    try:
        service = VacationNotificationService(
            calendar_provider=calendar_provider,
            email_provider=email_provider,
        )
        result = service.prepare_notifications(
            request=request,
            send_emails=args.send_emails,
        )
    except ValueError as error:
        raise SystemExit(f"Nie można przygotować powiadomień: {error}") from error

    print("Powiadomienia o nieobecnosci przygotowane.\n")
    print(f"Przeskanowane wydarzenia: {result.scanned_events}")
    print(f"Liczba uczniow do powiadomienia: {len(result.notices)}\n")

    for index, notice in enumerate(result.notices, start=1):
        print(f"[{index}] Uczeń: {notice.student_name}")
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
        student_notes_folder_id=selected_parent_folder_id
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
        print(f"Uczeń: {lesson.student_name}")
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
        student_notes_folder_id=selected_parent_folder_id
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
        print(f"Uczeń: {assignment.student_name}")
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
            console.print("Do widzenia!")
            return

        thinking_state = ThinkingStreamState()

        status.update("[bold green]Agent myśli...[/bold green]")
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

                output_text = event.text
                if event.kind == "tool_output":
                    output_text = (
                        output_text.replace("<tool_output>\n", "")
                        .replace("\n</tool_output>\n", "")
                        .replace("<tool_output>", "")
                        .replace("</tool_output>", "")
                    )

                visible_text, reasoning_text = _split_thinking_chunks(
                    output_text, thinking_state
                )
                visible_text = _apply_pending_visible_leading_newline_strip(
                    visible_text, thinking_state
                )

                if not visible_text and (not show_reasoning or not reasoning_text):
                    continue

                if not started_response:
                    if status_running:
                        status.stop()
                        status_running = False
                    console.print("[bold #e27d60]Agent>[/bold #e27d60]")
                    started_response = True

                if visible_text:
                    console.print(
                        visible_text,
                        end="",
                        highlight=False,
                        markup=False,
                    )
                if show_reasoning and reasoning_text:
                    console.print(
                        reasoning_text,
                        end="",
                        style="dim",
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

        final_visible, final_reasoning = _flush_thinking_state(thinking_state)
        final_visible = _apply_pending_visible_leading_newline_strip(
            final_visible, thinking_state
        )
        if final_visible or (show_reasoning and final_reasoning):
            if not started_response:
                console.print("[bold #e27d60]Agent>[/bold #e27d60]")
                started_response = True
            if final_visible:
                console.print(
                    final_visible,
                    end="",
                    highlight=False,
                    markup=False,
                )
            if show_reasoning and final_reasoning:
                console.print(
                    final_reasoning,
                    end="",
                    style="dim",
                    highlight=False,
                    markup=False,
                )

        if started_response:
            console.print()
            console.print()
            continue

        if show_reasoning:
            console.print("[dim]Agent zakończył zadanie bez treści odpowiedzi.[/dim]")
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


def _split_thinking_chunks(
    chunk: str, state: ThinkingStreamState
) -> tuple[str, str]:
    open_tag = "<thinking>"
    close_tag = "</thinking>"
    combined = state.carry + chunk
    state.carry = ""
    visible_parts: list[str] = []
    reasoning_parts: list[str] = []

    while combined:
        if state.inside_thinking:
            close_index = combined.find(close_tag)
            if close_index == -1:
                keep = len(close_tag) - 1
                if len(combined) > keep:
                    reasoning_parts.append(combined[:-keep])
                    state.carry = combined[-keep:]
                else:
                    state.carry = combined
                break

            reasoning_parts.append(combined[:close_index])
            combined = combined[close_index + len(close_tag) :]
            state.inside_thinking = False
            state.pending_strip_visible_leading_newlines = True
            continue

        open_index = combined.find(open_tag)
        if open_index == -1:
            keep = len(open_tag) - 1
            if len(combined) > keep:
                visible_parts.append(combined[:-keep])
                state.carry = combined[-keep:]
            else:
                state.carry = combined
            break

        visible_parts.append(combined[:open_index])
        combined = combined[open_index + len(open_tag) :]
        state.inside_thinking = True

    return "".join(visible_parts), "".join(reasoning_parts)


def _apply_pending_visible_leading_newline_strip(
    visible_text: str, state: ThinkingStreamState
) -> str:
    if not state.pending_strip_visible_leading_newlines:
        return visible_text
    stripped = visible_text.lstrip("\n\r")
    if stripped:
        state.pending_strip_visible_leading_newlines = False
    return stripped


def _flush_thinking_state(state: ThinkingStreamState) -> tuple[str, str]:
    if not state.carry:
        return "", ""

    tail = state.carry
    state.carry = ""
    if state.inside_thinking:
        return "", tail
    return tail, ""


def _print_tool_event(
    console: Console,
    tool_name: str,
    status: str | None,
    summary: str | None,
) -> None:
    if status == "error":
        style = "red"
        label = "Błąd"
    else:
        style = "grey70" if status == "pending" else "green"
        label = "Używam"

    text = Text()
    text.append(f"{label} [", style=style)
    text.append(tool_name, style=style)
    text.append("]", style=style)

    if status == "error" and summary:
        text.append(f" {summary}", style=style)

    console.print(text)


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

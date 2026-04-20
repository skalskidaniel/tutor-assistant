"""LangChain tools wrapping existing tutor assistant use cases."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
import os
from pathlib import Path
from typing import Literal

from langchain_core.tools import BaseTool, tool

from tutor_assistant.core import (
    GOOGLE_ONBOARDING_SCOPES,
    GoogleCalendarLessonProvider,
    create_google_desktop_credentials_file,
    load_google_credentials,
)
from tutor_assistant.daily_summary import (
    BedrockLessonInsightsProvider,
    DailySummaryService,
    GoogleDriveStudentNotesProvider,
    PyMuPdfRecentPagesProvider,
)
from tutor_assistant.drive_cleanup import DriveCleanupService, GoogleDriveCleanupProvider
from tutor_assistant.homework import (
    BedrockHomeworkMatcher,
    GoogleDriveHomeworkProvider,
    HomeworkService,
)
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


@dataclass(frozen=True)
class AgentToolDefaults:
    calendar_id: str = "primary"
    timezone: str = "Europe/Warsaw"
    meeting_duration_minutes: int = 60
    drive_parent_folder_id: str | None = None
    homework_db_folder_id: str | None = None
    max_concurrency: int = 4


def create_agent_tools(*, defaults: AgentToolDefaults | None = None) -> list[BaseTool]:
    resolved_defaults = defaults or AgentToolDefaults()
    default_drive_parent_folder_id = (
        resolved_defaults.drive_parent_folder_id
        or os.getenv("GOOGLE_DRIVE_PARENT_FOLDER_ID")
    )
    default_homework_db_folder_id = (
        resolved_defaults.homework_db_folder_id
        or os.getenv("GOOGLE_HOMEWORK_DATABASE_FOLDER_ID")
    )

    @tool
    def get_current_datetime() -> str:
        """Zwraca aktualna lokalna date, dzien tygodnia i godzine."""

        now = datetime.now().astimezone()
        weekday_map = {
            0: "poniedzialek",
            1: "wtorek",
            2: "sroda",
            3: "czwartek",
            4: "piatek",
            5: "sobota",
            6: "niedziela",
        }
        weekday_name = weekday_map[now.weekday()]
        return (
            f"Dzisiaj jest {weekday_name}, {now.date().isoformat()}. "
            f"Aktualna godzina: {now.strftime('%H:%M %Z')}."
        )

    @tool
    def get_agent_configuration() -> str:
        """Zwraca aktualna konfiguracje agenta i dostepow (kalendarz, Drive, pliki auth)."""

        credentials_path = Path(os.getenv("GOOGLE_CREDENTIALS_PATH", "credentials.json"))
        token_path = Path(os.getenv("GOOGLE_TOKEN_PATH", "token.json"))
        lines = [
            "Konfiguracja agenta:",
            f"- calendar_id (domyslnie): {resolved_defaults.calendar_id}",
            f"- timezone: {resolved_defaults.timezone}",
            f"- drive_parent_folder_id: {default_drive_parent_folder_id or 'brak'}",
            f"- homework_db_folder_id: {default_homework_db_folder_id or 'brak'}",
            f"- google_credentials_path: {credentials_path}",
            f"- credentials_file_exists: {'tak' if credentials_path.exists() else 'nie'}",
            f"- google_token_path: {token_path}",
            f"- token_file_exists: {'tak' if token_path.exists() else 'nie'}",
        ]
        return "\n".join(lines)

    @tool
    def login_google_user(
        client_id: str | None = None,
        client_secret: str | None = None,
        project_id: str | None = None,
        run_browser_auth: bool = True,
    ) -> str:
        """Tworzy credentials.json i opcjonalnie uruchamia logowanie Google uzytkownika."""

        try:
            credentials_path = Path(os.getenv("GOOGLE_CREDENTIALS_PATH", "credentials.json"))
            token_path = Path(os.getenv("GOOGLE_TOKEN_PATH", "token.json"))

            resolved_client_id = (
                client_id or os.getenv("GOOGLE_OAUTH_CLIENT_ID", "")
            ).strip()
            resolved_client_secret = (
                client_secret or os.getenv("GOOGLE_OAUTH_CLIENT_SECRET", "")
            ).strip()

            if resolved_client_id and resolved_client_secret:
                create_google_desktop_credentials_file(
                    credentials_path=credentials_path,
                    client_id=resolved_client_id,
                    client_secret=resolved_client_secret,
                    project_id=project_id or os.getenv("GOOGLE_OAUTH_PROJECT_ID"),
                )
            elif not credentials_path.exists():
                raise ValueError(
                    "Brak client_id/client_secret. Podaj je jawnie lub ustaw "
                    "GOOGLE_OAUTH_CLIENT_ID i GOOGLE_OAUTH_CLIENT_SECRET."
                )

            if run_browser_auth:
                load_google_credentials(
                    credentials_path=credentials_path,
                    token_path=token_path,
                    scopes=GOOGLE_ONBOARDING_SCOPES,
                )

            lines = [
                "Logowanie Google przygotowane pomyslnie.",
                f"credentials_path: {credentials_path}",
                f"token_path: {token_path}",
                f"credentials_file_exists: {'tak' if credentials_path.exists() else 'nie'}",
                f"token_file_exists: {'tak' if token_path.exists() else 'nie'}",
            ]
            if run_browser_auth:
                lines.append("OAuth wykonany (przegladarka uruchomiona lokalnie).")
            else:
                lines.append("OAuth pominiety (run_browser_auth=False).")
            return "\n".join(lines)
        except Exception as exc:  # noqa: BLE001
            return _tool_error_message(exc)

    @tool
    def onboard_student(
        first_name: str,
        last_name: str,
        email: str,
        phone: str,
        meeting_date: str,
        hour: int,
        minute: int,
        recurrence: Literal["none", "weekly", "biweekly"] = "weekly",
        occurrences: int | None = None,
        calendar_id: str | None = None,
        timezone: str | None = None,
        meeting_duration_minutes: int | None = None,
        drive_parent_folder_id: str | None = None,
    ) -> str:
        """Onboarduje nowego ucznia i tworzy link Meet oraz folder Drive."""

        try:
            request = NewStudentRequest(
                first_name=first_name,
                last_name=last_name,
                email=email,
                phone=phone,
            )
            schedule = MeetingSchedule(
                meeting_date=_parse_date_value(meeting_date, field_name="meeting_date"),
                hour=hour,
                minute=minute,
                recurrence=recurrence,
                occurrences=occurrences,
            )

            meet_provider = GoogleMeetProvider(
                calendar_id=calendar_id or resolved_defaults.calendar_id,
                timezone=timezone or resolved_defaults.timezone,
                meeting_duration_minutes=(
                    meeting_duration_minutes
                    if meeting_duration_minutes is not None
                    else resolved_defaults.meeting_duration_minutes
                ),
                schedule=schedule,
            )
            drive_provider = GoogleDriveProvider(
                parent_folder_id=drive_parent_folder_id or default_drive_parent_folder_id
            )

            service = StudentWelcomeService(
                meet_provider=meet_provider,
                drive_provider=drive_provider,
            )
            package = service.onboard_student(request)

            return (
                "Onboarding zakonczony pomyslnie.\n"
                f"Google Meet: {package.meet_link}\n"
                f"Google Drive: {package.drive_folder_url}\n"
                "Wiadomosc do ucznia:\n"
                f"{package.message_for_student}"
            )
        except Exception as exc:  # noqa: BLE001
            return _tool_error_message(exc)

    @tool
    def cleanup_drive(
        drive_parent_folder_id: str | None = None,
    ) -> str:
        """Czysci foldery uczniow na Google Drive (zadania i nazwy notatek)."""

        try:
            provider = GoogleDriveCleanupProvider(
                parent_folder_id=drive_parent_folder_id or default_drive_parent_folder_id
            )
            service = DriveCleanupService(provider=provider)
            result = service.cleanup()

            return (
                "Cleanup Google Drive zakonczony pomyslnie.\n"
                f"Przeskanowani uczniowie: {result.scanned_students}\n"
                f"Usuniete pliki z zadania-domowe: {result.deleted_files}\n"
                f"Zmienione nazwy plikow w notatki: {result.renamed_files}"
            )
        except Exception as exc:  # noqa: BLE001
            return _tool_error_message(exc)

    @tool
    def prepare_vacation_notifications(
        start_date: str,
        end_date: str | None = None,
        send_emails: bool = False,
        calendar_id: str | None = None,
    ) -> str:
        """Przygotowuje powiadomienia o nieobecnosci i opcjonalnie wysyla e-maile."""

        try:
            vacation_start = _parse_date_value(start_date, field_name="start_date")
            vacation_end = (
                _parse_date_value(end_date, field_name="end_date")
                if end_date
                else vacation_start
            )
            request = VacationRequest(start_date=vacation_start, end_date=vacation_end)

            calendar_provider = GoogleCalendarLessonProvider(
                calendar_id=calendar_id or resolved_defaults.calendar_id
            )
            email_provider = GmailProvider() if send_emails else None
            service = VacationNotificationService(
                calendar_provider=calendar_provider,
                email_provider=email_provider,
            )
            result = service.prepare_notifications(
                request=request,
                send_emails=send_emails,
            )

            lines = [
                "Powiadomienia o nieobecnosci przygotowane.",
                f"Przeskanowane wydarzenia: {result.scanned_events}",
                f"Liczba uczniow do powiadomienia: {len(result.notices)}",
            ]

            for index, notice in enumerate(result.notices, start=1):
                lines.append(
                    f"[{index}] Uczen: {notice.student_name}; "
                    f"Email: {notice.student_email or 'brak'}; "
                    f"Telefon: {notice.student_phone or 'brak'}"
                )
                if send_emails:
                    status = "wyslany" if notice.email_sent else "pominiety (brak e-maila)"
                    lines.append(f"Status e-maila: {status}")
                lines.append(f"Wiadomosc: {notice.message}")

            return "\n".join(lines)
        except Exception as exc:  # noqa: BLE001
            return _tool_error_message(exc)

    @tool
    def build_daily_summary(
        target_date: str | None = None,
        calendar_id: str | None = None,
        drive_parent_folder_id: str | None = None,
        max_concurrency: int | None = None,
    ) -> str:
        """Tworzy dzienne podsumowanie zajec na podstawie kalendarza i notatek PDF.

        Gdy chodzi o dzisiaj, pomin argument `target_date`.
        """

        try:
            selected_date = _parse_date_value(
                target_date,
                field_name="target_date",
                default_to_today=True,
            )

            calendar_provider = GoogleCalendarLessonProvider(
                calendar_id=calendar_id or resolved_defaults.calendar_id,
                include_drive_scope=True,
            )
            notes_provider = GoogleDriveStudentNotesProvider(
                parent_folder_id=drive_parent_folder_id or default_drive_parent_folder_id
            )
            pdf_recent_pages_provider = PyMuPdfRecentPagesProvider(recent_pages_count=3)
            insights_provider = BedrockLessonInsightsProvider()

            service = DailySummaryService(
                calendar_provider=calendar_provider,
                notes_provider=notes_provider,
                pdf_recent_pages_provider=pdf_recent_pages_provider,
                insights_provider=insights_provider,
                max_concurrency=(
                    max_concurrency
                    if max_concurrency is not None
                    else resolved_defaults.max_concurrency
                ),
            )
            result = service.build_summary_for_day(target_date=selected_date)

            lines = [
                f"Dzienne podsumowanie zajec dla: {selected_date.isoformat()}",
                f"Liczba zaplanowanych lekcji: {result.scanned_events}",
                f"Liczba podsumowan: {len(result.lesson_summaries)}",
            ]

            for index, lesson in enumerate(result.lesson_summaries, start=1):
                lesson_time = _format_lesson_time_range(
                    start=lesson.lesson_start_time,
                    end=lesson.lesson_end_time,
                )
                lines.append(
                    f"[{index}] Godzina: {lesson_time}; "
                    f"Uczen: {lesson.student_name}; "
                    f"Notatki PDF: {lesson.source_pdf_name or 'brak'}"
                )
                lines.append(f"Podsumowanie: {lesson.recent_notes_summary}")

            return "\n".join(lines)
        except Exception as exc:  # noqa: BLE001
            return _tool_error_message(exc)

    @tool
    def upload_homework_for_day(
        target_date: str | None = None,
        calendar_id: str | None = None,
        drive_parent_folder_id: str | None = None,
        homework_db_folder_id: str | None = None,
        max_concurrency: int | None = None,
    ) -> str:
        """Wybiera i uploaduje zadania domowe do folderow uczniow dla danego dnia.

        Gdy chodzi o dzisiaj, pomin argument `target_date`.
        """

        try:
            selected_date = _parse_date_value(
                target_date,
                field_name="target_date",
                default_to_today=True,
            )

            selected_parent_folder_id = (
                drive_parent_folder_id or default_drive_parent_folder_id
            )
            selected_homework_database_folder_id = (
                homework_db_folder_id or default_homework_db_folder_id
            )

            calendar_provider = GoogleCalendarLessonProvider(
                calendar_id=calendar_id or resolved_defaults.calendar_id,
                include_drive_scope=True,
            )
            notes_provider = GoogleDriveStudentNotesProvider(
                parent_folder_id=selected_parent_folder_id
            )
            pdf_recent_pages_provider = PyMuPdfRecentPagesProvider(recent_pages_count=3)
            insights_provider = BedrockLessonInsightsProvider()
            homework_drive_provider = GoogleDriveHomeworkProvider(
                parent_folder_id=selected_parent_folder_id,
                homework_database_folder_id=selected_homework_database_folder_id,
            )
            homework_matcher = BedrockHomeworkMatcher()

            service = HomeworkService(
                calendar_provider=calendar_provider,
                notes_provider=notes_provider,
                pdf_recent_pages_provider=pdf_recent_pages_provider,
                insights_provider=insights_provider,
                homework_drive_provider=homework_drive_provider,
                homework_matcher=homework_matcher,
                max_concurrency=(
                    max_concurrency
                    if max_concurrency is not None
                    else resolved_defaults.max_concurrency
                ),
            )
            result = service.upload_homework_for_day(target_date=selected_date)

            lines = [
                f"Upload zadan domowych dla: {selected_date.isoformat()}",
                f"Liczba zaplanowanych lekcji: {result.scanned_events}",
                f"Liczba przeslanych zadan: {result.uploaded_homeworks}",
            ]

            for index, assignment in enumerate(result.assignments, start=1):
                lesson_time = _format_lesson_time_range(
                    start=assignment.lesson_start_time,
                    end=assignment.lesson_end_time,
                )
                lines.append(
                    f"[{index}] Godzina: {lesson_time}; "
                    f"Uczen: {assignment.student_name}; "
                    f"Status: {assignment.status}"
                )
                lines.append(f"Szczegoly: {assignment.status_details}")
                lines.append(
                    f"Wgrane zadanie: {assignment.uploaded_homework_name or 'brak'}"
                )

            return "\n".join(lines)
        except Exception as exc:  # noqa: BLE001
            return _tool_error_message(exc)

    return [
        get_current_datetime,
        get_agent_configuration,
        login_google_user,
        onboard_student,
        cleanup_drive,
        prepare_vacation_notifications,
        build_daily_summary,
        upload_homework_for_day,
    ]


def _parse_date_value(
    value: str | None,
    *,
    field_name: str,
    default_to_today: bool = False,
) -> date:
    if value is None or not value.strip():
        if default_to_today:
            return date.today()
        raise ValueError(f"Pole {field_name} jest wymagane.")

    normalized = value.strip().casefold()
    if normalized in {
        "dzis",
        "dzisiaj",
        "today",
        "wstaw_tu_date_dzisiejsza",
    }:
        return date.today()
    if normalized in {"jutro", "tomorrow"}:
        return date.today() + timedelta(days=1)
    if normalized in {"wczoraj", "yesterday"}:
        return date.today() - timedelta(days=1)

    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(
            f"Pole {field_name} musi miec format YYYY-MM-DD. Otrzymano: {value}"
        ) from exc


def _tool_error_message(error: Exception) -> str:
    return f"Wystapil blad podczas wykonania narzedzia: {error}"


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

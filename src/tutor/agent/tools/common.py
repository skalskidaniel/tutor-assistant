import os
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from functools import wraps
from threading import Lock
from typing import Callable

import dateparser
from strands import tool


MAX_TOOL_SELF_REPAIR_ATTEMPTS = 3
TOOL_ERROR_PREFIX = "Wystąpił błąd podczas wykonania narzędzia"


class ToolUserActionRequiredError(Exception):
    """Raised when the tool requires explicit user approval first."""


@dataclass
class _FailureTracker:
    failures: int = 0
    lock: Lock = field(default_factory=Lock)

    def mark_success(self) -> None:
        with self.lock:
            self.failures = 0

    def mark_failure(self) -> int:
        with self.lock:
            self.failures += 1
            return self.failures


def agent_tool(func: Callable[..., object]) -> Callable[..., object]:
    tracker = _FailureTracker()

    @wraps(func)
    def guarded(*args: object, **kwargs: object) -> object:
        try:
            result = func(*args, **kwargs)
        except ToolUserActionRequiredError as error:
            tracker.mark_success()
            return build_user_action_required_message(error=error)
        except Exception as error:  # noqa: BLE001
            failure_count = tracker.mark_failure()
            return build_tool_failure_message(
                error=error,
                failure_count=failure_count,
            )

        tracker.mark_success()
        return result

    return tool(guarded)


def parse_date_value(
    value: str | None,
    *,
    field_name: str,
    default_to_today: bool = False,
) -> date:
    if value is None or not value.strip():
        if default_to_today:
            return date.today()
        raise ValueError(f"Pole {field_name} jest wymagane.")

    stripped_value = value.strip()
    normalized = _normalize_relative_date_keyword(stripped_value)
    if normalized in {
        "dzis",
        "dzisiaj",
        "today",
        "wstaw_tu_date_dzisiejsza",
    }:
        return date.today()
    if normalized in {"jutro", "tomorrow"} or normalized.startswith("jutrzejsz"):
        return date.today() + timedelta(days=1)
    if normalized in {"wczoraj", "yesterday"} or normalized.startswith("wczorajsz"):
        return date.today() - timedelta(days=1)

    try:
        return date.fromisoformat(stripped_value)
    except ValueError:
        pass

    cleaned_value = stripped_value.lower()
    for prefix in ["w przyszły ", "przyszły ", "w najbliższy ", "najbliższy ", "w nastepny ", "w następny "]:
        if cleaned_value.startswith(prefix):
            cleaned_value = cleaned_value[len(prefix):]
            
    parsed = dateparser.parse(
        cleaned_value,
        languages=["pl", "en"],
        settings={"PREFER_DATES_FROM": "future", "STRICT_PARSING": False, "RELATIVE_BASE": datetime.now()},
    )
    if parsed is not None:
        return parsed.date()

    raise ValueError(
        f"Pole {field_name} musi miec format YYYY-MM-DD lub byc zrozumiala data (np. 'przyszly wtorek'). Otrzymano: {value}"
    )


def _normalize_relative_date_keyword(value: str) -> str:
    return value.casefold().strip(" \t\n\r.,;:!?\"'`()[]{}")


def resolve_oauth_value(*, explicit_value: str | None, env_var_name: str) -> str:
    explicit = (explicit_value or "").strip()
    if explicit and not looks_like_placeholder(explicit):
        return explicit

    fallback = os.getenv(env_var_name, "").strip()
    return fallback if not looks_like_placeholder(fallback) else ""


def resolve_runtime_value(
    *,
    explicit_value: str | None,
    fallback_value: str | None,
) -> str | None:
    explicit = (explicit_value or "").strip()
    if explicit and not looks_like_placeholder(explicit):
        return explicit

    fallback = (fallback_value or "").strip()
    if fallback and not looks_like_placeholder(fallback):
        return fallback

    return None


def looks_like_placeholder(value: str) -> bool:
    normalized = value.casefold().strip()
    if not normalized:
        return False

    markers = (
        "wstaw",
        "placeholder",
        "twoj_",
        "twoje_",
        "your_",
        "<",
        ">",
    )
    return any(marker in normalized for marker in markers)


def build_tool_failure_message(
    *,
    error: Exception,
    failure_count: int,
    max_failures: int = MAX_TOOL_SELF_REPAIR_ATTEMPTS,
) -> str:
    base = f"{TOOL_ERROR_PREFIX}: {error}"
    if failure_count < max_failures:
        return (
            f"{base}\n"
            "AUTONAPRAWA: Przeanalizuj błąd i spróbuj ponownie wywołać to samo "
            "narzędzie z poprawionymi argumentami. "
            f"To próba {failure_count} z {max_failures}."
        )

    return (
        f"{base}\n"
        f"AUTONAPRAWA: Osiągnięto limit {max_failures} błędnych prób. "
        "Nie próbuj ponownie. Zgłoś błąd użytkownikowi i poproś o poprawkę "
        "danych albo decyzje."
    )


def build_user_action_required_message(*, error: Exception) -> str:
    return (
        f"{TOOL_ERROR_PREFIX}: {error}\n"
        "AUTONAPRAWA: To nie jest błąd techniczny. Nie ponawiaj automatycznie. "
        "Najpierw uzyskaj decyzje użytkownika i dopiero wtedy wykonaj narzędzie ponownie."
    )


def require_user_approval(*, approved_by_user: bool, operation: str) -> None:
    if approved_by_user:
        return

    raise ToolUserActionRequiredError(
        "Wymagana jest wyraźna zgoda użytkownika przed operacją krytyczną: "
        f"{operation}. Zapytaj o potwierdzenie i po zgodzie wywołaj narzędzie "
        "ponownie z approved_by_user=true."
    )


def format_lesson_time_range(
    *,
    start: datetime | None,
    end: datetime | None,
) -> str:
    if start is None:
        return "brak"

    start_label = format_clock_time(start)
    if end is None:
        return start_label

    end_label = format_clock_time(end)
    return f"{start_label}-{end_label}"


def format_clock_time(value: datetime) -> str:
    if value.tzinfo is None:
        return value.strftime("%H:%M")
    return value.astimezone().strftime("%H:%M")

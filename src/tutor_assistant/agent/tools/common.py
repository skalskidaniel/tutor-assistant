import os
from datetime import date, datetime, timedelta
from typing import Callable

from strands import tool

try:
    from langsmith import traceable
except Exception:  # noqa: BLE001

    def traceable(*_args: object, **_kwargs: object):
        def _decorator(func: object) -> object:
            return func

        return _decorator


def agent_tool(func: Callable[..., object]) -> Callable[..., object]:
    """Decorator to wrap a function as an agent tool with tracing."""
    return tool(traceable(run_type="tool", name=func.__name__)(func))


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
    except ValueError as exc:
        raise ValueError(
            f"Pole {field_name} musi miec format YYYY-MM-DD. Otrzymano: {value}"
        ) from exc


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


def tool_error_message(error: Exception) -> str:
    return f"Wystapil blad podczas wykonania narzedzia: {error}"


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

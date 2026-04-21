"""Shared core utilities and integrations."""

from .auth import (
    GOOGLE_CALENDAR_DRIVE_SCOPES,
    GOOGLE_ONBOARDING_SCOPES,
    GOOGLE_VACATION_SCOPES,
    create_google_desktop_credentials_file,
    ensure_google_credentials_file,
    load_google_credentials,
)
from .calendar import (
    CalendarLessonEvent,
    GoogleCalendarLessonProvider,
    LessonCalendarProvider,
)
from .memory import DEFAULT_MEMORY_NAMESPACE, MemoryService
from .models import Student
from .utils import slugify, resolve_required_path, extract_bedrock_text, format_http_error

__all__ = [
    "CalendarLessonEvent",
    "GOOGLE_CALENDAR_DRIVE_SCOPES",
    "GOOGLE_ONBOARDING_SCOPES",
    "GOOGLE_VACATION_SCOPES",
    "create_google_desktop_credentials_file",
    "ensure_google_credentials_file",
    "GoogleCalendarLessonProvider",
    "LessonCalendarProvider",
    "load_google_credentials",
    "DEFAULT_MEMORY_NAMESPACE",
    "MemoryService",
    "slugify",
    "Student",
    "resolve_required_path",
    "extract_bedrock_text",
    "format_http_error"
]

"""Shared core utilities and integrations."""

from .auth import (
    GOOGLE_CALENDAR_DRIVE_SCOPES,
    GOOGLE_ONBOARDING_SCOPES,
    GOOGLE_VACATION_SCOPES,
    load_google_credentials,
)
from .calendar import (
    CalendarLessonEvent,
    GoogleCalendarLessonProvider,
    InMemoryLessonCalendarProvider,
    LessonCalendarProvider,
)
from .utils import slugify

__all__ = [
    "CalendarLessonEvent",
    "GOOGLE_CALENDAR_DRIVE_SCOPES",
    "GOOGLE_ONBOARDING_SCOPES",
    "GOOGLE_VACATION_SCOPES",
    "GoogleCalendarLessonProvider",
    "InMemoryLessonCalendarProvider",
    "LessonCalendarProvider",
    "load_google_credentials",
    "slugify",
]

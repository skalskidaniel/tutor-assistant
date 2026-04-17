"""Use case 3: vacation notifications."""

from .models import (
    CalendarLessonEvent,
    StudentVacationNotice,
    VacationRequest,
    VacationResult,
)
from .providers import (
    GmailProvider,
    GoogleCalendarLessonProvider,
    InMemoryEmailProvider,
    InMemoryLessonCalendarProvider,
    LessonCalendarProvider,
    StudentEmailProvider,
)
from .service import VacationNotificationService

__all__ = [
    "CalendarLessonEvent",
    "GmailProvider",
    "GoogleCalendarLessonProvider",
    "InMemoryEmailProvider",
    "InMemoryLessonCalendarProvider",
    "LessonCalendarProvider",
    "StudentEmailProvider",
    "StudentVacationNotice",
    "VacationNotificationService",
    "VacationRequest",
    "VacationResult",
]

"""Vacation notifications package"""

from tutor.core.calendar import (
    CalendarLessonEvent,
    GoogleCalendarLessonProvider,
    InMemoryLessonCalendarProvider,
    LessonCalendarProvider,
)

from .models import StudentVacationNotice, VacationRequest, VacationResult
from .providers import (
    GmailProvider,
    InMemoryEmailProvider,
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

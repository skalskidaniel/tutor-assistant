"""Vacation notifications package"""

from tutor.core.calendar import (
    CalendarLessonEvent,
    GoogleCalendarLessonProvider,
    LessonCalendarProvider,
)

from .models import StudentVacationNotice, VacationRequest, VacationResult
from .providers import (
    GmailProvider,
    StudentEmailProvider,
)
from .service import VacationNotificationService

__all__ = [
    "CalendarLessonEvent",
    "GmailProvider",
    "GoogleCalendarLessonProvider",
    "LessonCalendarProvider",
    "StudentEmailProvider",
    "StudentVacationNotice",
    "VacationNotificationService",
    "VacationRequest",
    "VacationResult",
]

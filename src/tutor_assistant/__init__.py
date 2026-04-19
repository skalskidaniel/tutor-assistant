"""Tutor Assistant package."""

from .drive_cleanup import (
    DriveCleanupResult,
    DriveCleanupService,
    GoogleDriveCleanupProvider,
)
from .daily_summary import (
    BedrockLessonInsightsProvider,
    DailyLessonSummary,
    DailySummaryResult,
    DailySummaryService,
    GoogleDriveStudentNotesProvider,
    PyMuPdfRecentPagesProvider,
)
from .onboarding import (
    GoogleDriveProvider,
    GoogleMeetProvider,
    InMemoryDriveProvider,
    InMemoryMeetProvider,
    MeetingSchedule,
    NewStudentRequest,
    StudentWelcomeService,
    WelcomePackage,
    slugify,
)
from .vacation import (
    CalendarLessonEvent,
    GmailProvider,
    GoogleCalendarLessonProvider,
    StudentVacationNotice,
    VacationNotificationService,
    VacationRequest,
    VacationResult,
)

__all__ = [
    "DriveCleanupResult",
    "DriveCleanupService",
    "GoogleDriveCleanupProvider",
    "BedrockLessonInsightsProvider",
    "DailyLessonSummary",
    "DailySummaryResult",
    "DailySummaryService",
    "GoogleDriveStudentNotesProvider",
    "PyMuPdfRecentPagesProvider",
    "GoogleDriveProvider",
    "GoogleMeetProvider",
    "InMemoryDriveProvider",
    "InMemoryMeetProvider",
    "MeetingSchedule",
    "NewStudentRequest",
    "StudentWelcomeService",
    "StudentVacationNotice",
    "VacationNotificationService",
    "VacationRequest",
    "VacationResult",
    "WelcomePackage",
    "CalendarLessonEvent",
    "GoogleCalendarLessonProvider",
    "GmailProvider",
    "slugify",
]

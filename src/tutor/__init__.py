"""Tutor package."""

from .core import CalendarLessonEvent, GoogleCalendarLessonProvider
from .daily_summary import (
    BedrockLessonInsightsProvider,
    DailyLessonSummary,
    DailySummaryResult,
    DailySummaryService,
    GoogleDriveStudentNotesProvider,
    PyMuPdfRecentPagesProvider,
)
from .drive_cleanup import (
    DriveCleanupResult,
    DriveCleanupService,
    GoogleDriveCleanupProvider,
)
from .homework import (
    BedrockHomeworkMatcher,
    GoogleDriveHomeworkProvider,
    HomeworkAssignment,
    HomeworkService,
    HomeworkUploadResult,
)
from .onboarding import (
    GoogleDriveProvider,
    GoogleMeetProvider,
    InMemoryDriveProvider,
    InMemoryMeetProvider,
    MeetingSchedule,
    Student,
    StudentWelcomeService,
    WelcomePackage,
    slugify,
)
from .vacation import (
    GmailProvider,
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
    "BedrockHomeworkMatcher",
    "GoogleDriveHomeworkProvider",
    "HomeworkAssignment",
    "HomeworkService",
    "HomeworkUploadResult",
    "GoogleDriveProvider",
    "GoogleMeetProvider",
    "InMemoryDriveProvider",
    "InMemoryMeetProvider",
    "MeetingSchedule",
    "Student",
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

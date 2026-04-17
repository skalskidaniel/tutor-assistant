"""Tutor Assistant package."""

from .drive_cleanup import (
    DriveCleanupResult,
    DriveCleanupService,
    GoogleDriveCleanupProvider,
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

__all__ = [
    "DriveCleanupResult",
    "DriveCleanupService",
    "GoogleDriveCleanupProvider",
    "GoogleDriveProvider",
    "GoogleMeetProvider",
    "InMemoryDriveProvider",
    "InMemoryMeetProvider",
    "MeetingSchedule",
    "NewStudentRequest",
    "StudentWelcomeService",
    "WelcomePackage",
    "slugify",
]

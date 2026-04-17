"""Onboarding package for new student flow."""

from .models import MeetingSchedule, NewStudentRequest, WelcomePackage, slugify
from .providers import (
    DriveProvider,
    GoogleDriveProvider,
    GoogleMeetProvider,
    InMemoryDriveProvider,
    InMemoryMeetProvider,
    MeetProvider,
)
from .service import StudentWelcomeService

__all__ = [
    "DriveProvider",
    "GoogleDriveProvider",
    "GoogleMeetProvider",
    "InMemoryDriveProvider",
    "InMemoryMeetProvider",
    "MeetingSchedule",
    "MeetProvider",
    "NewStudentRequest",
    "StudentWelcomeService",
    "WelcomePackage",
    "slugify",
]

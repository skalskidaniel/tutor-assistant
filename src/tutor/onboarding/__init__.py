"""Onboarding package for welcoming a new student."""

from tutor.core import slugify

from .models import MeetingSchedule, Student, WelcomePackage
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
    "Student",
    "StudentWelcomeService",
    "WelcomePackage",
    "slugify",
]

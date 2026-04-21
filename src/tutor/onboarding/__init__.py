"""Onboarding package for welcoming a new student."""

from tutor.core import slugify
from tutor.core import Student

from .models import MeetingSchedule, WelcomePackage
from .providers import (
    DriveProvider,
    GoogleDriveProvider,
    GoogleMeetProvider,
    MeetProvider,
)
from .service import StudentWelcomeService

__all__ = [
    "DriveProvider",
    "GoogleDriveProvider",
    "GoogleMeetProvider",
    "MeetingSchedule",
    "MeetProvider",
    "Student",
    "StudentWelcomeService",
    "WelcomePackage",
    "slugify",
]

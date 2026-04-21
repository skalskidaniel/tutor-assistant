"""Homework management package"""

from .models import (
    DriveFile,
    HomeworkAssignment,
    HomeworkUploadResult,
)
from .providers import (
    BedrockHomeworkMatcher,
    GoogleDriveHomeworkProvider,
    HomeworkDriveProvider,
    HomeworkMatcher,
)
from .service import HomeworkService

__all__ = [
    "BedrockHomeworkMatcher",
    "DriveFile",
    "GoogleDriveHomeworkProvider",
    "HomeworkAssignment",
    "HomeworkDriveProvider",
    "HomeworkMatcher",
    "HomeworkService",
    "HomeworkUploadResult",
]

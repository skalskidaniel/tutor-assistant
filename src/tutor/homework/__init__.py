"""Homework management package"""

from .models import (
    CopiedHomeworkFile,
    HomeworkAssignment,
    HomeworkDatabaseFile,
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
    "CopiedHomeworkFile",
    "GoogleDriveHomeworkProvider",
    "HomeworkAssignment",
    "HomeworkDatabaseFile",
    "HomeworkDriveProvider",
    "HomeworkMatcher",
    "HomeworkService",
    "HomeworkUploadResult",
]

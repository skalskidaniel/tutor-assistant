import os
from typing import Callable

from tutor_assistant.core import GoogleCalendarLessonProvider
from tutor_assistant.daily_summary import (
    BedrockLessonInsightsProvider,
    DailySummaryService,
    GoogleDriveStudentNotesProvider,
    PyMuPdfRecentPagesProvider,
)
from tutor_assistant.drive_cleanup import (
    DriveCleanupService,
    GoogleDriveCleanupProvider,
)
from tutor_assistant.homework import (
    BedrockHomeworkMatcher,
    GoogleDriveHomeworkProvider,
    HomeworkService,
)
from tutor_assistant.onboarding import (
    GoogleDriveProvider,
    GoogleMeetProvider,
    StudentWelcomeService,
)
from tutor_assistant.vacation import (
    GmailProvider,
    VacationNotificationService,
)

from .auth import make_login_google_user_tool
from .drive_cleanup import make_cleanup_drive_tool
from .homework import make_upload_homework_for_day_tool
from .models import AgentToolDefaults
from .onboarding import make_onboard_student_tool
from .summary import make_build_daily_summary_tool
from .system import make_get_agent_configuration_tool, make_get_current_datetime_tool
from .vacation import make_prepare_vacation_notifications_tool

__all__ = [
    "AgentToolDefaults",
    "create_agent_tools",
]


def create_agent_tools(
    *, defaults: AgentToolDefaults | None = None
) -> list[Callable[..., object]]:
    resolved_defaults = defaults or AgentToolDefaults()
    default_drive_parent_folder_id = (
        resolved_defaults.drive_parent_folder_id
        or os.getenv("GOOGLE_DRIVE_PARENT_FOLDER_ID")
    )
    default_homework_db_folder_id = (
        resolved_defaults.homework_db_folder_id
        or os.getenv("GOOGLE_HOMEWORK_DATABASE_FOLDER_ID")
    )

    # Instantiate Providers
    calendar_provider = GoogleCalendarLessonProvider(
        calendar_id=resolved_defaults.calendar_id,
        include_drive_scope=True,
    )
    vacation_calendar_provider = GoogleCalendarLessonProvider(
        calendar_id=resolved_defaults.calendar_id,
    )
    notes_provider = GoogleDriveStudentNotesProvider(
        parent_folder_id=default_drive_parent_folder_id
    )
    pdf_recent_pages_provider = PyMuPdfRecentPagesProvider(recent_pages_count=3)
    insights_provider = BedrockLessonInsightsProvider()

    homework_drive_provider = GoogleDriveHomeworkProvider(
        parent_folder_id=default_drive_parent_folder_id,
        homework_database_folder_id=default_homework_db_folder_id,
    )
    homework_matcher = BedrockHomeworkMatcher()

    cleanup_provider = GoogleDriveCleanupProvider(
        parent_folder_id=default_drive_parent_folder_id
    )

    meet_provider = GoogleMeetProvider(
        calendar_id=resolved_defaults.calendar_id,
        timezone=resolved_defaults.timezone,
        meeting_duration_minutes=resolved_defaults.meeting_duration_minutes,
    )
    onboarding_drive_provider = GoogleDriveProvider(
        parent_folder_id=default_drive_parent_folder_id
    )
    email_provider = GmailProvider()

    # Instantiate Services
    daily_summary_service = DailySummaryService(
        calendar_provider=calendar_provider,
        notes_provider=notes_provider,
        pdf_recent_pages_provider=pdf_recent_pages_provider,
        insights_provider=insights_provider,
        max_concurrency=resolved_defaults.max_concurrency,
        progress_callback=resolved_defaults.progress_callback,
    )

    homework_service = HomeworkService(
        calendar_provider=calendar_provider,
        notes_provider=notes_provider,
        pdf_recent_pages_provider=pdf_recent_pages_provider,
        insights_provider=insights_provider,
        homework_drive_provider=homework_drive_provider,
        homework_matcher=homework_matcher,
        max_concurrency=resolved_defaults.max_concurrency,
        progress_callback=resolved_defaults.progress_callback,
    )

    drive_cleanup_service = DriveCleanupService(provider=cleanup_provider)

    vacation_service = VacationNotificationService(
        calendar_provider=vacation_calendar_provider,
        email_provider=email_provider,
    )

    onboarding_service = StudentWelcomeService(
        meet_provider=meet_provider,
        drive_provider=onboarding_drive_provider,
    )

    return [
        make_get_current_datetime_tool(),
        make_get_agent_configuration_tool(
            defaults=resolved_defaults,
            default_drive_parent_folder_id=default_drive_parent_folder_id,
            default_homework_db_folder_id=default_homework_db_folder_id,
        ),
        make_login_google_user_tool(),
        make_onboard_student_tool(onboarding_service),
        make_cleanup_drive_tool(drive_cleanup_service),
        make_prepare_vacation_notifications_tool(vacation_service),
        make_build_daily_summary_tool(daily_summary_service),
        make_upload_homework_for_day_tool(homework_service),
    ]

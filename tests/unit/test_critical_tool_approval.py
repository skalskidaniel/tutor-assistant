from datetime import date
from typing import Callable, cast

from tutor.agent.tools.onboarding import (  # pyright: ignore[reportMissingImports]
    make_onboard_student_tool,
)
from tutor.agent.tools.vacation import (  # pyright: ignore[reportMissingImports]
    make_prepare_vacation_notifications_tool,
)
from tutor.core import Student
from tutor.onboarding import MeetingSchedule, StudentWelcomeService, WelcomePackage
from tutor.vacation import VacationNotificationService, VacationRequest, VacationResult


class _FakeOnboardingService:
    def onboard_student(self, request: Student, schedule: MeetingSchedule) -> WelcomePackage:
        return WelcomePackage(
            meet_link="https://meet.google.com/test",
            drive_folder_url="https://drive.google.com/drive/folders/test",
            message_for_student=(
                f"Czesc {request.first_name}, Twoja lekcja: "
                f"{schedule.meeting_date.isoformat()} {schedule.hour:02d}:{schedule.minute:02d}"
            ),
        )


class _FakeVacationService:
    def prepare_notifications(
        self,
        *,
        request: VacationRequest,
        send_emails: bool,
    ) -> VacationResult:
        assert request.start_date <= request.end_date
        return VacationResult(scanned_events=0, notices=())


def _call_tool(tool: object, **kwargs: object) -> str:
    for name in ("invoke", "run", "__call__"):
        candidate = getattr(tool, name, None)
        if callable(candidate):
            if name == "__call__":
                return tool(**kwargs)  # type: ignore[misc,operator]
            return cast(Callable[..., str], candidate)(**kwargs)
    raise AssertionError("Nie udalo sie uruchomic narzedzia w tescie.")


def test_onboard_student_requires_approval_before_calendar_save() -> None:
    tool = make_onboard_student_tool(cast(StudentWelcomeService, _FakeOnboardingService()))

    response = _call_tool(
        tool,
        first_name="Jan",
        last_name="Kowalski",
        email="jan@example.com",
        phone="+48500100200",
        meeting_date=date.today().isoformat(),
        hour=18,
        minute=0,
        approved_by_user=False,
    )

    assert "Wymagana jest wyraźna zgoda użytkownika" in response
    assert "approved_by_user=true" in response


def test_onboard_student_runs_after_approval() -> None:
    tool = make_onboard_student_tool(cast(StudentWelcomeService, _FakeOnboardingService()))

    response = _call_tool(
        tool,
        first_name="Jan",
        last_name="Kowalski",
        email="jan@example.com",
        phone="+48500100200",
        meeting_date=date.today().isoformat(),
        hour=18,
        minute=0,
        approved_by_user=True,
    )

    assert "Onboarding zakończony pomyślnie." in response


def test_prepare_vacation_notifications_requires_approval_only_for_email_send() -> None:
    tool = make_prepare_vacation_notifications_tool(cast(VacationNotificationService, _FakeVacationService()))

    response_without_send = _call_tool(
        tool,
        start_date=date.today().isoformat(),
        send_emails=False,
        approved_by_user=False,
    )
    assert "Powiadomienia o nieobecności przygotowane." in response_without_send

    response_with_send = _call_tool(
        tool,
        start_date=date.today().isoformat(),
        send_emails=True,
        approved_by_user=False,
    )
    assert "Wymagana jest wyraźna zgoda użytkownika" in response_with_send


def test_prepare_vacation_notifications_runs_when_send_approved() -> None:
    tool = make_prepare_vacation_notifications_tool(cast(VacationNotificationService, _FakeVacationService()))

    response = _call_tool(
        tool,
        start_date=date.today().isoformat(),
        send_emails=True,
        approved_by_user=True,
    )

    assert "Powiadomienia o nieobecności przygotowane." in response


def test_prepare_vacation_notifications_end_date_validation_still_works() -> None:
    tool = make_prepare_vacation_notifications_tool(cast(VacationNotificationService, _FakeVacationService()))

    response = _call_tool(
        tool,
        start_date="2026-07-10",
        end_date="2026-07-01",
        send_emails=False,
    )

    assert "Wystąpił błąd podczas wykonania narzędzia" in response
    assert "To próba 1 z 3." in response


def test_tool_failure_message_stops_after_third_attempt() -> None:
    tool = make_prepare_vacation_notifications_tool(cast(VacationNotificationService, _FakeVacationService()))

    for _ in range(2):
        first_or_second = _call_tool(
            tool,
            start_date="2026-07-10",
            end_date="2026-07-01",
            send_emails=False,
        )
        assert "To próba" in first_or_second

    third = _call_tool(
        tool,
        start_date="2026-07-10",
        end_date="2026-07-01",
        send_emails=False,
    )
    assert "Osiągnięto limit 3 błędnych prób." in third
    assert "Nie próbuj ponownie." in third


def test_tool_failure_counter_resets_after_success() -> None:
    tool = make_prepare_vacation_notifications_tool(cast(VacationNotificationService, _FakeVacationService()))

    _call_tool(
        tool,
        start_date="2026-07-10",
        end_date="2026-07-01",
        send_emails=False,
    )
    success = _call_tool(
        tool,
        start_date="2026-07-10",
        end_date="2026-07-10",
        send_emails=False,
    )
    assert "Powiadomienia o nieobecności przygotowane." in success

    after_reset = _call_tool(
        tool,
        start_date="2026-07-10",
        end_date="2026-07-01",
        send_emails=False,
    )
    assert "To próba 1 z 3." in after_reset

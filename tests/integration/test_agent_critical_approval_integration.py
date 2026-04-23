from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, cast

import pytest

from tutor.agent.graph import (  # pyright: ignore[reportMissingImports]
    _extract_tool_statuses,
    _format_passthrough_tool_output,
    _is_passthrough_tool,
)
from tutor.agent.session import AgentChatSession
from tutor.core import Student
from tutor.onboarding import MeetingSchedule, StudentWelcomeService, WelcomePackage
from tutor.agent.tools.onboarding import make_onboard_student_tool
from strands import Agent


@dataclass
class _RecordingOnboardingService:
    calls: int = 0

    def onboard_student(self, request: Student, schedule: MeetingSchedule) -> WelcomePackage:
        self.calls += 1
        return WelcomePackage(
            meet_link="https://meet.google.com/test-link",
            drive_folder_url="https://drive.google.com/drive/folders/test-folder",
            message_for_student=(
                f"Czesc {request.first_name}, start: "
                f"{schedule.meeting_date.isoformat()} {schedule.hour:02d}:{schedule.minute:02d}"
            ),
        )


class _FakeApprovalAwareAgent:
    def __init__(self, *, onboarding_tool: Any) -> None:
        self._onboarding_tool = onboarding_tool
        self._waiting_for_approval = False

    def stream_async(self, user_input: str) -> Any:
        async def _generator() -> Any:
            approved = self._is_approval_message(user_input)
            should_approve = self._waiting_for_approval and approved
            if should_approve:
                self._waiting_for_approval = False

            tool_use_id = "onboard-1"
            yield {
                "current_tool_use": {
                    "name": "onboard_student",
                    "toolUseId": tool_use_id,
                }
            }

            result = self._onboarding_tool(
                first_name="Jan",
                last_name="Kowalski",
                email="jan@example.com",
                phone="+48500100200",
                meeting_date=date.today().isoformat(),
                hour=18,
                minute=0,
                approved_by_user=should_approve,
            )
            status = (
                "error"
                if "Wystąpił błąd podczas wykonania narzędzia" in result
                else "completed"
            )
            yield {
                "message": {
                    "role": "user",
                    "content": [
                        {
                            "toolResult": {
                                "toolUseId": tool_use_id,
                                "status": status,
                                "content": [{"text": result}],
                            }
                        }
                    ],
                }
            }

            if (
                status == "error"
                and "Wymagana jest wyrazna zgoda użytkownika" in result
            ):
                self._waiting_for_approval = True
                yield {
                    "data": "Potrzebuję Twojej zgody na zapisanie lekcji. Napisz: tak."
                }

        return _generator()

    def __call__(self, user_input: str) -> str:
        # Fallback for direct calls (used by session.ask when streaming not used)
        # This is a simplified version - in reality we'd need to handle async properly
        # but for test purposes we'll just return a basic response
        if "Zrob onboarding ucznia" in user_input:
            return "Potrzebuję Twojej zgody na zapisanie lekcji. Napisz: tak."
        elif user_input.strip().casefold() in {"tak", "zgoda", "potwierdzam"}:
            return self._onboarding_tool(
                first_name="Jan",
                last_name="Kowalski",
                email="jan@example.com",
                phone="+48500100200",
                meeting_date=date.today().isoformat(),
                hour=18,
                minute=0,
                approved_by_user=True,
            )
        return "Nieznana komenda"

    @staticmethod
    def _is_approval_message(user_input: str) -> bool:
        return user_input.strip().casefold() in {"tak", "zgoda", "potwierdzam"}


@pytest.mark.integration
def test_agent_requires_explicit_approval_before_onboarding_execution() -> None:
    service = _RecordingOnboardingService()
    onboarding_tool = make_onboard_student_tool(cast(StudentWelcomeService, service))
    app = _FakeApprovalAwareAgent(onboarding_tool=onboarding_tool)
    session = AgentChatSession(
        app=cast(Agent, app),
        extract_tool_statuses=lambda event, names: _extract_tool_statuses(
            event=event,
            tool_names_by_use_id=names,
        ),
        is_passthrough_tool=_is_passthrough_tool,
        format_passthrough_tool_output=_format_passthrough_tool_output,
    )

    first_response = session.ask("Zrob onboarding ucznia")
    assert "Potrzebuję Twojej zgody" in first_response
    assert service.calls == 0

    second_response = session.ask("tak")
    assert "Onboarding zakończony pomyślnie." in second_response
    assert service.calls == 1

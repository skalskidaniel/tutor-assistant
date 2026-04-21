from typing import Callable

from tutor_assistant.homework import HomeworkService
from .common import (
    agent_tool,
    format_lesson_time_range,
    parse_date_value,
    tool_error_message,
)


def make_upload_homework_for_day_tool(
    service: HomeworkService,
) -> Callable[..., object]:
    @agent_tool
    def upload_homework_for_day(
        target_date: str | None = None,
    ) -> str:
        """Wybiera i uploaduje zadania domowe do folderow uczniow dla danego dnia.

        Gdy chodzi o dzisiaj, pomin argument `target_date`.
        """
        try:
            selected_date = parse_date_value(
                target_date,
                field_name="target_date",
                default_to_today=True,
            )

            result = service.upload_homework_for_day(target_date=selected_date)

            lines = [
                f"Upload zadan domowych dla: {selected_date.isoformat()}",
                f"Liczba zaplanowanych lekcji: {result.scanned_events}",
                f"Liczba przeslanych zadan: {result.uploaded_homeworks}",
            ]

            for index, assignment in enumerate(result.assignments, start=1):
                lesson_time = format_lesson_time_range(
                    start=assignment.lesson_start_time,
                    end=assignment.lesson_end_time,
                )
                lines.append(
                    f"[{index}] Godzina: {lesson_time}\n"
                    f"Uczen: {assignment.student_name}\n"
                    f"Status: {assignment.status}"
                )
                lines.append(f"Szczegoly: {assignment.status_details}")
                lines.append(
                    f"Wgrane zadanie: {assignment.uploaded_homework_name or 'brak'}"
                )

            return "\n".join(lines)
        except Exception as exc:  # noqa: BLE001
            return tool_error_message(exc)

    return upload_homework_for_day

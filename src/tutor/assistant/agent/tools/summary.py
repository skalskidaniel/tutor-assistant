from typing import Callable

from tutor.daily_summary import DailySummaryService
from .common import (
    agent_tool,
    format_lesson_time_range,
    parse_date_value,
    tool_error_message,
)


def make_build_daily_summary_tool(
    service: DailySummaryService,
) -> Callable[..., object]:
    @agent_tool
    def build_daily_summary(
        target_date: str | None = None,
    ) -> str:
        """Tworzy dzienne podsumowanie zajęć na podstawie kalendarza i notatek PDF.

        Gdy chodzi o dzisiaj, pomiń argument `target_date`.
        """
        try:
            selected_date = parse_date_value(
                target_date,
                field_name="target_date",
                default_to_today=True,
            )

            result = service.build_summary_for_day(target_date=selected_date)

            lines = [
                f"Dzienne podsumowanie zajęć dla: {selected_date.isoformat()}",
                f"Liczba zaplanowanych lekcji: {result.scanned_events}",
                f"Liczba podsumowań: {len(result.lesson_summaries)}",
            ]

            for index, lesson in enumerate(result.lesson_summaries, start=1):
                lesson_time = format_lesson_time_range(
                    start=lesson.lesson_start_time,
                    end=lesson.lesson_end_time,
                )
                lines.append(
                    f"[{index}] Godzina: {lesson_time}\n"
                    f"Uczeń: {lesson.student_name}\n"
                    f"Notatki w PDF: {lesson.source_pdf_name or 'brak'}"
                )
                lines.append(f"Podsumowanie notatek:\n{lesson.recent_notes_summary}")

            return "\n".join(lines)
        except Exception as exc:  # noqa: BLE001
            return tool_error_message(exc)

    return build_daily_summary

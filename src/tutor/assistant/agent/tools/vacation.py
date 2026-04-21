from typing import Callable

from tutor.vacation import (
    VacationNotificationService,
    VacationRequest,
)
from .common import agent_tool, parse_date_value, tool_error_message


def make_prepare_vacation_notifications_tool(
    service: VacationNotificationService,
) -> Callable[..., object]:
    @agent_tool
    def prepare_vacation_notifications(
        start_date: str,
        end_date: str | None = None,
        send_emails: bool = False,
    ) -> str:
        """Przygotowuje powiadomienia o nieobecności i opcjonalnie wysyła e-maile."""
        try:
            vacation_start = parse_date_value(start_date, field_name="start_date")
            vacation_end = (
                parse_date_value(end_date, field_name="end_date")
                if end_date
                else vacation_start
            )
            request = VacationRequest(start_date=vacation_start, end_date=vacation_end)

            result = service.prepare_notifications(
                request=request,
                send_emails=send_emails,
            )

            lines = [
                "Powiadomienia o nieobecności przygotowane.",
                f"Przeskanowane wydarzenia: {result.scanned_events}",
                f"Liczba uczniów do powiadomienia: {len(result.notices)}",
            ]

            for index, notice in enumerate(result.notices, start=1):
                lines.append(
                    f"[{index}] Uczeń: {notice.student_name}\n"
                    f"Email: {notice.student_email or 'brak'}\n"
                    f"Telefon: {notice.student_phone or 'brak'}"
                )
                if send_emails:
                    status = (
                        "wysłany" if notice.email_sent else "pominięty (brak e-maila)"
                    )
                    lines.append(f"Status e-maila: {status}")
                lines.append(f"Wiadomość: {notice.message}")

            return "\n".join(lines)
        except Exception as exc:  # noqa: BLE001
            return tool_error_message(exc)

    return prepare_vacation_notifications

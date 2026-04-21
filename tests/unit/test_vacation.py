from __future__ import annotations

from datetime import date

from tutor.vacation import (  # pyright: ignore[reportMissingImports]
    CalendarLessonEvent,
    InMemoryEmailProvider,
    InMemoryLessonCalendarProvider,
    VacationNotificationService,
    VacationRequest,
)


def test_prepare_notifications_groups_dates_and_includes_contact_data() -> None:
    provider = InMemoryLessonCalendarProvider(
        events=[
            CalendarLessonEvent(
                student_name="Jan Kowalski",
                lesson_date=date(2026, 7, 1),
                student_email="jan@example.com",
                student_phone="+48500100200",
            ),
            CalendarLessonEvent(
                student_name="Jan Kowalski",
                lesson_date=date(2026, 7, 8),
                student_email="jan@example.com",
                student_phone="+48500100200",
            ),
            CalendarLessonEvent(
                student_name="Anna Nowak",
                lesson_date=date(2026, 7, 2),
                student_email="anna@example.com",
                student_phone="+48500100300",
            ),
        ]
    )
    service = VacationNotificationService(
        calendar_provider=provider,
        schedule_url="https://example.com/schedule",
    )

    result = service.prepare_notifications(
        request=VacationRequest(start_date=date(2026, 7, 1), end_date=date(2026, 7, 8)),
        send_emails=False,
    )

    assert result.scanned_events == 3
    assert len(result.notices) == 2

    jan_notice = [
        notice for notice in result.notices if notice.student_name == "Jan Kowalski"
    ][0]
    assert jan_notice.lesson_dates == (date(2026, 7, 1), date(2026, 7, 8))
    assert jan_notice.student_phone == "+48500100200"
    assert jan_notice.student_email == "jan@example.com"
    assert "01.07.2026, 08.07.2026" in jan_notice.message
    assert jan_notice.email_sent is False


def test_prepare_notifications_sends_emails_when_enabled() -> None:
    calendar_provider = InMemoryLessonCalendarProvider(
        events=[
            CalendarLessonEvent(
                student_name="Jan Kowalski",
                lesson_date=date(2026, 7, 1),
                student_email="jan@example.com",
                student_phone="+48500100200",
            ),
            CalendarLessonEvent(
                student_name="Uczeń Bez Maila",
                lesson_date=date(2026, 7, 1),
                student_email=None,
                student_phone="+48500999888",
            ),
        ]
    )
    email_provider = InMemoryEmailProvider()
    service = VacationNotificationService(
        calendar_provider=calendar_provider,
        email_provider=email_provider,
        schedule_url="https://example.com/schedule",
    )

    result = service.prepare_notifications(
        request=VacationRequest(start_date=date(2026, 7, 1), end_date=date(2026, 7, 1)),
        send_emails=True,
    )

    assert len(email_provider.sent_messages) == 1
    recipient, subject, body = email_provider.sent_messages[0]
    assert recipient == "jan@example.com"
    assert subject == "Zmiana terminu zajęć"
    assert "01.07.2026" in body

    jan_notice = [
        notice for notice in result.notices if notice.student_name == "Jan Kowalski"
    ][0]
    no_email_notice = [
        notice for notice in result.notices if notice.student_name == "Uczeń Bez Maila"
    ][0]
    assert jan_notice.email_sent is True
    assert no_email_notice.email_sent is False


def test_prepare_notifications_requires_email_provider_when_send_enabled() -> None:
    calendar_provider = InMemoryLessonCalendarProvider(
        events=[
            CalendarLessonEvent(
                student_name="Jan Kowalski",
                lesson_date=date(2026, 7, 1),
                student_email="jan@example.com",
                student_phone="+48500100200",
            )
        ]
    )
    service = VacationNotificationService(
        calendar_provider=calendar_provider,
        schedule_url="https://example.com/schedule",
    )

    try:
        service.prepare_notifications(
            request=VacationRequest(
                start_date=date(2026, 7, 1), end_date=date(2026, 7, 1)
            ),
            send_emails=True,
        )
    except ValueError as error:
        assert "email_provider" in str(error)
    else:
        raise AssertionError("Oczekiwano ValueError dla braku email_provider.")

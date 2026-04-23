import pytest
from datetime import date, timedelta
from tutor.agent.tools.common import parse_date_value

def test_parse_date_value_exact_iso() -> None:
    assert parse_date_value("2024-05-15", field_name="test") == date(2024, 5, 15)

def test_parse_date_value_hardcoded_relative() -> None:
    today = date.today()
    assert parse_date_value("dzis", field_name="test") == today
    assert parse_date_value("jutro", field_name="test") == today + timedelta(days=1)
    assert parse_date_value("wczoraj", field_name="test") == today - timedelta(days=1)

def test_parse_date_value_dateparser_relative() -> None:
    # Przyszły wtorek będzie gdzieś w przyszłości
    parsed = parse_date_value("w przyszły wtorek", field_name="test")
    assert parsed > date.today()
    assert parsed.weekday() == 1  # 0 to poniedziałek, 1 to wtorek

def test_parse_date_value_invalid() -> None:
    with pytest.raises(ValueError, match="musi miec format YYYY-MM-DD lub byc zrozumiala data"):
        parse_date_value("nieznana data xd", field_name="test")

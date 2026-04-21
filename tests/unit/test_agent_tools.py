from datetime import date

from tutor.agent.tools.common import (
    looks_like_placeholder as _looks_like_placeholder,
    parse_date_value as _parse_date_value,
    resolve_oauth_value as _resolve_oauth_value,
    resolve_runtime_value as _resolve_runtime_value,
)


def test_parse_date_value_supports_relative_tomorrow_variants() -> None:
    today = date.today()

    assert _parse_date_value("jutro", field_name="target_date") == today.fromordinal(
        today.toordinal() + 1
    )
    assert _parse_date_value("jutrzejsza", field_name="target_date") == today.fromordinal(
        today.toordinal() + 1
    )
    assert _parse_date_value("jutrzejszej", field_name="target_date") == today.fromordinal(
        today.toordinal() + 1
    )
    assert _parse_date_value("tomorrow.", field_name="target_date") == today.fromordinal(
        today.toordinal() + 1
    )


def test_parse_date_value_supports_relative_yesterday_variants() -> None:
    today = date.today()

    assert _parse_date_value(
        "wczoraj", field_name="target_date"
    ) == today.fromordinal(today.toordinal() - 1)
    assert _parse_date_value(
        "wczorajsza", field_name="target_date"
    ) == today.fromordinal(today.toordinal() - 1)
    assert _parse_date_value(
        "wczorajszej", field_name="target_date"
    ) == today.fromordinal(today.toordinal() - 1)
    assert _parse_date_value(
        "yesterday,", field_name="target_date"
    ) == today.fromordinal(today.toordinal() - 1)


def test_looks_like_placeholder_detects_common_markers() -> None:
    assert _looks_like_placeholder("WSTAW_GOOGLE_OAUTH_CLIENT_ID")
    assert _looks_like_placeholder("<YOUR_CLIENT_SECRET>")
    assert not _looks_like_placeholder("1234-abcdef.apps.googleusercontent.com")


def test_resolve_oauth_value_ignores_placeholder_and_uses_env(monkeypatch) -> None:
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_ID", "real-client-id")

    resolved = _resolve_oauth_value(
        explicit_value="WSTAW_GOOGLE_OAUTH_CLIENT_ID",
        env_var_name="GOOGLE_OAUTH_CLIENT_ID",
    )

    assert resolved == "real-client-id"


def test_resolve_oauth_value_prefers_real_explicit_value(monkeypatch) -> None:
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_ID", "env-client-id")

    resolved = _resolve_oauth_value(
        explicit_value="explicit-client-id",
        env_var_name="GOOGLE_OAUTH_CLIENT_ID",
    )

    assert resolved == "explicit-client-id"


def test_resolve_runtime_value_uses_fallback_for_placeholder_explicit() -> None:
    resolved = _resolve_runtime_value(
        explicit_value="WSTAW_CALENDAR_ID",
        fallback_value="primary",
    )

    assert resolved == "primary"


def test_resolve_runtime_value_returns_none_for_placeholder_inputs() -> None:
    resolved = _resolve_runtime_value(
        explicit_value="WSTAW_DRIVE_PARENT_FOLDER_ID",
        fallback_value="WSTAW_FALLBACK",
    )

    assert resolved is None

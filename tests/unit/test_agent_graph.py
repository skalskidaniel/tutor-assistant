from datetime import date, timedelta

from tutor_assistant.agent.graph import (  # pyright: ignore[reportMissingImports]
    _format_passthrough_tool_output,
    _infer_relative_date_hint,
    _is_passthrough_tool,
    _prepare_user_input,
)


def test_infer_relative_date_hint_for_tomorrow() -> None:
    hint = _infer_relative_date_hint("Z kim mam zajecia jutro?")

    assert hint is not None
    assert hint["tool_value"] == "jutro"
    assert hint["iso_date"] == (date.today() + timedelta(days=1)).isoformat()


def test_prepare_user_input_adds_target_date_instruction_for_relative_day() -> None:
    prompt = _prepare_user_input("Czy mam jutrzejsze lekcje?")

    assert "[UWAGA DLA ASYSTENTA:" in prompt
    assert "target_date='jutro'" in prompt


def test_prepare_user_input_leaves_non_relative_prompt_unchanged() -> None:
    original = "Podaj konfiguracje agenta"
    assert _prepare_user_input(original) == original


def test_is_passthrough_tool_includes_target_tools() -> None:
    assert _is_passthrough_tool("build_daily_summary") is True
    assert _is_passthrough_tool("onboard_student") is True
    assert _is_passthrough_tool("prepare_vacation_notifications") is True
    assert _is_passthrough_tool("get_agent_configuration") is False


def test_format_passthrough_tool_output_wraps_raw_output_without_changes() -> None:
    raw_output = "Linia 1\nLinia 2"

    formatted = _format_passthrough_tool_output(raw_output)

    assert formatted == "<tool_output>\nLinia 1\nLinia 2\n</tool_output>\n"

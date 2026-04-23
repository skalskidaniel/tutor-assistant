from tutor.agent.tools.common import (  # pyright: ignore[reportMissingImports]
    MAX_TOOL_SELF_REPAIR_ATTEMPTS,
    TOOL_ERROR_PREFIX,
    build_tool_failure_message,
)


def test_build_tool_failure_message_includes_retry_instruction_before_limit() -> None:
    message = build_tool_failure_message(
        error=ValueError("zly format daty"),
        failure_count=2,
    )

    assert TOOL_ERROR_PREFIX in message
    assert "To próba 2 z 3." in message
    assert "spróbuj ponownie wywołać to samo narzędzie" in message


def test_build_tool_failure_message_includes_stop_instruction_at_limit() -> None:
    message = build_tool_failure_message(
        error=ValueError("nadal niepoprawne dane"),
        failure_count=MAX_TOOL_SELF_REPAIR_ATTEMPTS,
    )

    assert f"Osiągnięto limit {MAX_TOOL_SELF_REPAIR_ATTEMPTS} błędnych prób." in message
    assert "Nie próbuj ponownie." in message
    assert "Zgłoś błąd użytkownikowi" in message

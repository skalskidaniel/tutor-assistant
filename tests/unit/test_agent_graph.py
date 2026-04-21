from tutor.agent.graph import (  # pyright: ignore[reportMissingImports]
    _build_system_prompt,
    _format_passthrough_tool_output,
    _is_passthrough_tool,
    _resolve_memory_namespace,
)
from tutor.core.memory import MemoryService


def test_is_passthrough_tool_includes_target_tools() -> None:
    assert _is_passthrough_tool("build_daily_summary") is True
    assert _is_passthrough_tool("onboard_student") is True
    assert _is_passthrough_tool("prepare_vacation_notifications") is True
    assert _is_passthrough_tool("get_agent_configuration") is False


def test_format_passthrough_tool_output_wraps_raw_output_without_changes() -> None:
    raw_output = "Linia 1\nLinia 2"

    formatted = _format_passthrough_tool_output(raw_output)

    assert formatted == "<tool_output>\nLinia 1\nLinia 2\n</tool_output>\n"


def test_resolve_memory_namespace_returns_default_for_blank_thread_id() -> None:
    assert _resolve_memory_namespace("   ") == "teacher-cli"


def test_build_system_prompt_includes_saved_memory(monkeypatch, tmp_path) -> None:
    memory_file = tmp_path / "agent-memory.json"
    monkeypatch.setenv("TUTOR_AGENT_MEMORY_PATH", str(memory_file))

    memory_service = MemoryService(memory_path=memory_file)
    memory_service.set(namespace="teacher-cli", key="styl", value="krotko")

    prompt = _build_system_prompt(thread_id="teacher-cli")

    assert "<agent_memory>" in prompt
    assert "- styl: krotko" in prompt
    assert "</agent_memory>" in prompt

from argparse import Namespace
import importlib
from types import SimpleNamespace

from tutor.agent.cli import (  # pyright: ignore[reportMissingImports]
    _initialize_line_editing,
    _run_memory_delete,
    _run_memory_list,
    _run_memory_set,
    build_parser,
)


def test_build_parser_supports_memory_commands() -> None:
    parser = build_parser()

    set_args = parser.parse_args(["memory-set", "--key", "styl", "--value", "krotko"])
    assert set_args.command == "memory-set"
    assert set_args.key == "styl"
    assert set_args.value == "krotko"

    list_args = parser.parse_args(["memory-list"])
    assert list_args.command == "memory-list"

    delete_args = parser.parse_args(["memory-delete", "--key", "styl"])
    assert delete_args.command == "memory-delete"
    assert delete_args.key == "styl"


def test_memory_cli_roundtrip(monkeypatch, tmp_path, capsys) -> None:
    memory_path = tmp_path / "agent-memory.json"
    monkeypatch.setenv("TUTOR_AGENT_MEMORY_PATH", str(memory_path))

    _run_memory_set(Namespace(thread_id="teacher-cli", key="styl", value="krotko"))
    _run_memory_list(Namespace(thread_id="teacher-cli"))
    output_after_set = capsys.readouterr().out

    assert "- styl: krotko" in output_after_set

    _run_memory_delete(Namespace(thread_id="teacher-cli", key="styl"))
    _run_memory_list(Namespace(thread_id="teacher-cli"))
    output_after_delete = capsys.readouterr().out

    assert "Status: usunieto" in output_after_delete
    assert "(pusto)" in output_after_delete


def test_initialize_line_editing_binds_tab_completion_when_readline_available(
    monkeypatch,
) -> None:
    calls: list[str] = []

    fake_readline = SimpleNamespace(parse_and_bind=lambda value: calls.append(value))
    monkeypatch.setattr(
        importlib, "import_module", lambda name: fake_readline if name == "readline" else None
    )

    _initialize_line_editing()

    assert calls == ["tab: complete"]


def test_initialize_line_editing_noop_when_readline_unavailable(monkeypatch) -> None:
    def _raise_module_not_found(name: str) -> None:
        raise ModuleNotFoundError(name)

    monkeypatch.setattr(importlib, "import_module", _raise_module_not_found)

    _initialize_line_editing()

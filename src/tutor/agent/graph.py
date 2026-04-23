from __future__ import annotations

import os
from typing import Any, Literal

from strands import Agent
from strands.models import BedrockModel
from tutor.core.memory import DEFAULT_MEMORY_NAMESPACE, MemoryService

from .session import AgentChatSession, _extract_text_from_tool_result_content
from .tools import AgentToolDefaults, create_agent_tools


DEFAULT_AGENT_MODEL_ID = "amazon.nova-lite-v1:0"
PASSTHROUGH_TOOL_NAMES = {
    "build_daily_summary",
    "onboard_student",
    "prepare_vacation_notifications",
}
SYSTEM_PROMPT = (
    "Jesteś asystentem nauczyciela matematyki. "
    "Odpowiadaj tylko po polsku, krótko i rzeczowo. "
    "\n"
    "## Narzędzia\n"
    "Masz dostęp do narzędzi Google, pamięci i czasu. "
    "Gdy zadanie wymaga działania na Google Calendar, Drive lub Gmail, użyj narzędzia zamiast zgadywać. "
    "Jeśli brakuje credentials.json albo token.json, najpierw użyj login_google_user. "
    "Jeśli do login_google_user potrzebne są dane OAuth, poproś o GOOGLE_OAUTH_CLIENT_ID i GOOGLE_OAUTH_CLIENT_SECRET. "
    "Nie mów, że nie masz dostępu, dopóki nie spróbujesz właściwego narzędzia. "
    "\n"
    "## Daty\n"
    "Nie używaj placeholderów dat. "
    "Wszystkie daty podawaj w formacie YYYY-MM-DD. "
    "Nie używaj słów 'dzisiaj' ani 'jutro'; w razie potrzeby użyj get_current_datetime i sam przelicz datę. "
    "\n"
    "## Krytyczne akcje\n"
    "Przed onboard_student zawsze uzyskaj zgodę użytkownika. "
    "Przed prepare_vacation_notifications uzyskaj zgodę tylko gdy send_emails=true. "
    "Po zgodzie ustaw approved_by_user=true. "
    "Dla narzędzi niekrytycznych działaj od razu. "
    "\n"
    "## Strict passthrough\n"
    "Dla build_daily_summary, onboard_student i prepare_vacation_notifications zwracaj wynik dokładnie 1:1 jako "
    "<tool_output>...</tool_output> bez żadnego dodatkowego tekstu. "
    "\n"
    "## Błędy\n"
    "Przy błędzie najpierw spróbuj samonaprawy: sprawdź błąd, popraw argumenty albo wykonaj autoryzację przez login_google_user. "
    "Wykonaj maksymalnie 3 próby. "
    "Jeśli nadal jest błąd, pokaż użytkownikowi pełny komunikat. "
    "\n"
    "## Pamięć\n"
    "Do zapisywania preferencji i ustawień użyj save_to_memory. "
    "Do usuwania użyj delete_from_memory. "
    "Do przypominania ustawień użyj read_memory."
)


def build_agent_app(
    *,
    defaults: AgentToolDefaults | None = None,
    thread_id: str = DEFAULT_MEMORY_NAMESPACE,
) -> Agent:
    memory_namespace = _resolve_memory_namespace(thread_id)
    tools = create_agent_tools(
        defaults=defaults,
        memory_namespace=memory_namespace,
    )
    system_prompt = _build_system_prompt(thread_id=thread_id)
    model = BedrockModel(
        model_id=_resolve_agent_model_id(),
        region_name=_resolve_region_name(),
        temperature=0.4,
        max_tokens=1200,
    )
    return Agent(
        model=model,
        tools=tools,
        callback_handler=None,
        system_prompt=system_prompt,
    )


def build_chat_session(
    *,
    defaults: AgentToolDefaults | None = None,
    thread_id: str = "teacher-cli",
) -> AgentChatSession:
    app = build_agent_app(defaults=defaults, thread_id=thread_id)
    return AgentChatSession(
        app=app,
        thread_id=thread_id,
        extract_tool_statuses=lambda event, names: _extract_tool_statuses(
            event=event,
            tool_names_by_use_id=names,
        ),
        is_passthrough_tool=_is_passthrough_tool,
        format_passthrough_tool_output=_format_passthrough_tool_output,
    )


def resolve_agent_model_id() -> str:
    """Expose the model id used by the chat agent runtime."""

    return _resolve_agent_model_id()


def _resolve_agent_model_id() -> str:
    return os.getenv("BEDROCK_AGENT_MODEL_ID", DEFAULT_AGENT_MODEL_ID).split("/")[-1]


def _resolve_region_name() -> str:
    return os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION", "eu-central-1")


def _extract_tool_statuses(
    *,
    event: dict[str, Any],
    tool_names_by_use_id: dict[str, str],
) -> list[tuple[str, Literal["completed", "error"], str]]:
    message = event.get("message")
    if not isinstance(message, dict):
        return []
    if message.get("role") != "user":
        return []

    statuses: list[tuple[str, Literal["completed", "error"], str]] = []
    blocks = message.get("content")
    if not isinstance(blocks, list):
        return statuses

    for block in blocks:
        if not isinstance(block, dict):
            continue

        tool_result = block.get("toolResult")
        if not isinstance(tool_result, dict):
            continue

        tool_use_id = tool_result.get("toolUseId")
        if not isinstance(tool_use_id, str):
            continue

        tool_name = tool_names_by_use_id.get(tool_use_id)
        if not tool_name:
            continue

        content = _extract_text_from_tool_result_content(tool_result.get("content"))
        status_raw = tool_result.get("status")
        status: Literal["completed", "error"]
        if (
            status_raw == "error"
            or _is_tool_error_content(content)
        ):
            status = "error"
        else:
            status = "completed"

        summary = content
        if not _is_passthrough_tool(tool_name):
            summary = _summarize_tool_content(content)
        statuses.append((tool_name, status, summary))

    return statuses

def _summarize_tool_content(content: str) -> str:
    cleaned = " ".join(part.strip() for part in content.splitlines() if part.strip())
    if not cleaned:
        return "Brak wyniku."

    if len(cleaned) <= 140:
        return cleaned

    truncated = cleaned[:137].rsplit(" ", 1)[0].rstrip()
    return f"{truncated}..."


def _is_tool_error_content(content: str) -> bool:
    return (
        "Wystapil blad podczas wykonania narzedzia" in content
        or "Wystąpił błąd podczas wykonania narzędzia" in content
    )


def _is_passthrough_tool(tool_name: str) -> bool:
    return tool_name in PASSTHROUGH_TOOL_NAMES


def _format_passthrough_tool_output(raw_output: str) -> str:
    return f"<tool_output>\n{raw_output}\n</tool_output>\n"


def _build_system_prompt(*, thread_id: str) -> str:
    namespace = _resolve_memory_namespace(thread_id)
    memory_service = MemoryService()
    entries = memory_service.get_all(namespace=namespace)
    if not entries:
        return SYSTEM_PROMPT

    memory_lines = ["<agent_memory>"]
    for key in sorted(entries):
        memory_lines.append(f"- {key}: {entries[key]}")
    memory_lines.append("</agent_memory>")
    return f"{SYSTEM_PROMPT}\n\n" + "\n".join(memory_lines)


def _resolve_memory_namespace(thread_id: str) -> str:
    value = thread_id.strip()
    return value if value else DEFAULT_MEMORY_NAMESPACE

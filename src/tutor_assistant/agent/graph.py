"""Strands-based orchestration for interactive tutor assistant chat."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import date, timedelta
import os
from queue import Queue
from threading import Thread
from typing import Any, Iterator, Literal

from strands import Agent
from strands.models import BedrockModel

from .tools import AgentToolDefaults, create_agent_tools

try:
    from langsmith import traceable
except Exception:  # noqa: BLE001
    def traceable(*_args: Any, **_kwargs: Any):
        def _decorator(func: Any) -> Any:
            return func

        return _decorator


DEFAULT_AGENT_MODEL_ID = "anthropic.claude-3-haiku-20240307-v1:0"
PASSTHROUGH_TOOL_NAMES = {
    "build_daily_summary",
    "onboard_student",
    "prepare_vacation_notifications",
}
SYSTEM_PROMPT = (
    "Jestes asystentem nauczyciela matematyki. "
    "Rozmawiaj po polsku i odpowiadaj zwiezle. "
    "Masz aktywne dostepy przez lokalne credentials/token i narzedzia. "
    "Nie pisz, ze nie masz dostepu, dopoki nie sprobowales wywolac odpowiedniego narzedzia. "
    "Gdy brakuje credentials.json albo token.json, najpierw uzyj login_google_user. "
    "Jesli login_google_user potrzebuje danych OAuth, popros uzytkownika o GOOGLE_OAUTH_CLIENT_ID i GOOGLE_OAUTH_CLIENT_SECRET. "
    "Nigdy nie tworz placeholderow dat typu WSTAW_... i podobnych. "
    "Gdy prosba wymaga dzialania na Google Calendar/Drive/Gmail, "
    "uzywaj dostepnych narzedzi zamiast zgadywac wynik. "
    "WAZNE: Dla narzedzi build_daily_summary, onboard_student i "
    "prepare_vacation_notifications obowiazuje STRICT PASSTHROUGH. "
    "Nie wolno modyfikowac ich wyniku ani jednego znaku. "
    "Zwracaj go dokladnie 1:1, opakowany w znaczniki: "
    "<tool_output> ... </tool_output>. "
    "Nie dodawaj zadnego tekstu przed ani po tych znacznikach."
)


@dataclass(frozen=True)
class ChatStreamEvent:
    """Single event produced while streaming an agent response."""

    kind: Literal["token", "tool", "tool_output"]
    text: str
    status: Literal["pending", "completed", "error"] | None = None
    summary: str | None = None


@dataclass
class AgentChatSession:
    """Stateful chat session around a Strands agent."""

    app: Agent
    thread_id: str = "teacher-cli"

    def stream(self, user_input: str) -> Iterator[ChatStreamEvent]:
        if not user_input.strip():
            return

        prepared_input = _prepare_user_input(user_input)
        stream_queue: Queue[ChatStreamEvent | Exception | object] = Queue()
        done_marker = object()

        async def _collect_events() -> None:
            async_stream = self.app.stream_async(prepared_input)
            tool_names_by_use_id: dict[str, str] = {}
            seen_pending: set[str] = set()
            seen_terminal: set[str] = set()
            passthrough_emitted = False

            try:
                async for event in async_stream:
                    current_tool = event.get("current_tool_use")
                    if isinstance(current_tool, dict):
                        tool_name = current_tool.get("name")
                        tool_use_id = current_tool.get("toolUseId")
                        if isinstance(tool_name, str) and tool_name:
                            if isinstance(tool_use_id, str) and tool_use_id:
                                tool_names_by_use_id[tool_use_id] = tool_name
                            if tool_name not in seen_pending:
                                seen_pending.add(tool_name)
                                stream_queue.put(
                                    ChatStreamEvent(
                                        kind="tool",
                                        text=tool_name,
                                        status="pending",
                                    )
                                )

                    for tool_name, status, summary in _extract_tool_statuses(
                        event=event,
                        tool_names_by_use_id=tool_names_by_use_id,
                    ):
                        key = f"{tool_name}:{status}:{summary}"
                        if key in seen_terminal:
                            continue
                        seen_terminal.add(key)
                        stream_queue.put(
                            ChatStreamEvent(
                                kind="tool",
                                text=tool_name,
                                status=status,
                                summary=summary,
                            )
                        )

                        if (
                            _is_passthrough_tool(tool_name)
                            and status == "completed"
                            and isinstance(summary, str)
                            and not passthrough_emitted
                        ):
                            passthrough_emitted = True
                            stream_queue.put(
                                ChatStreamEvent(
                                    kind="tool_output",
                                    text=_format_passthrough_tool_output(summary),
                                )
                            )

                    if passthrough_emitted:
                        continue

                    token = event.get("data")
                    if isinstance(token, str) and token:
                        stream_queue.put(ChatStreamEvent(kind="token", text=token))
            except Exception as exc:  # noqa: BLE001
                stream_queue.put(exc)
            finally:
                await async_stream.aclose()
                stream_queue.put(done_marker)

        worker = Thread(target=lambda: asyncio.run(_collect_events()), daemon=True)
        worker.start()

        while True:
            item = stream_queue.get()
            if item is done_marker:
                break
            if isinstance(item, Exception):
                raise item
            yield item

        worker.join()

    @traceable(run_type="chain", name="chat_session_ask")
    def ask(self, user_input: str) -> str:
        chunks: list[str] = []
        for event in self.stream(user_input):
            if event.kind in {"token", "tool_output"}:
                chunks.append(event.text)

        text = "".join(chunks).strip()
        if text:
            return text

        result = self.app(_prepare_user_input(user_input))
        resolved = _extract_text_from_agent_result(result).strip()
        return resolved or "Gotowe."


def build_agent_app(*, defaults: AgentToolDefaults | None = None) -> Agent:
    tools = create_agent_tools(defaults=defaults)
    model = BedrockModel(
        model_id=_resolve_agent_model_id(),
        region_name=_resolve_region_name(),
        temperature=0,
        max_tokens=1200,
    )
    return Agent(
        model=model,
        tools=tools,
        callback_handler=None,
        system_prompt=SYSTEM_PROMPT,
    )


def build_chat_session(
    *,
    defaults: AgentToolDefaults | None = None,
    thread_id: str = "teacher-cli",
) -> AgentChatSession:
    app = build_agent_app(defaults=defaults)
    return AgentChatSession(app=app, thread_id=thread_id)


def resolve_agent_model_id() -> str:
    """Expose the model id used by the chat agent runtime."""

    return _resolve_agent_model_id()


def _resolve_agent_model_id() -> str:
    return os.getenv(
        "BEDROCK_AGENT_MODEL_ID",
        os.getenv("BEDROCK_MODEL_ID", DEFAULT_AGENT_MODEL_ID),
    )


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
        if status_raw == "error" or "Wystapil blad podczas wykonania narzedzia" in content:
            status = "error"
        else:
            status = "completed"

        summary = content
        if not _is_passthrough_tool(tool_name):
            summary = _summarize_tool_content(content)
        statuses.append((tool_name, status, summary))

    return statuses


def _extract_text_from_tool_result_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""

    fragments: list[str] = []
    for item in content:
        if isinstance(item, str):
            fragments.append(item)
            continue
        if isinstance(item, dict):
            text = item.get("text")
            if isinstance(text, str):
                fragments.append(text)
    return "".join(fragments)


def _extract_text_from_agent_result(result: Any) -> str:
    message = getattr(result, "message", None)
    if isinstance(message, str) and message.strip():
        return message

    last_message = getattr(result, "last_message", None)
    if isinstance(last_message, dict):
        content = last_message.get("content")
        text = _extract_text_from_tool_result_content(content)
        if text.strip():
            return text

    result_text = str(result)
    return result_text if result_text != "None" else ""


def _summarize_tool_content(content: str) -> str:
    cleaned = " ".join(part.strip() for part in content.splitlines() if part.strip())
    if not cleaned:
        return "Brak wyniku."

    if len(cleaned) <= 140:
        return cleaned

    truncated = cleaned[:137].rsplit(" ", 1)[0].rstrip()
    return f"{truncated}..."


def _is_passthrough_tool(tool_name: str) -> bool:
    return tool_name in PASSTHROUGH_TOOL_NAMES


def _format_passthrough_tool_output(raw_output: str) -> str:
    return f"<tool_output>\n{raw_output}\n</tool_output>\n"


def _prepare_user_input(user_input: str) -> str:
    hint = _infer_relative_date_hint(user_input)
    if hint is None:
        return user_input

    return (
        f"{user_input}\n\n"
        "[UWAGA DLA ASYSTENTA: To pytanie dotyczy daty wzglednej. "
        f"Zinterpretowana data: {hint['iso_date']}. "
        "Przy uzyciu narzedzia build_daily_summary lub upload_homework_for_day "
        f"USTAW target_date='{hint['tool_value']}' "
        f"(mozna tez uzyc ISO: {hint['iso_date']}). "
        "Nie pomijaj target_date w tym zapytaniu.]"
    )


def _infer_relative_date_hint(user_input: str) -> dict[str, str] | None:
    normalized = user_input.casefold()

    if any(keyword in normalized for keyword in ("pojutrze", "day after tomorrow")):
        target = date.today() + timedelta(days=2)
        return {"tool_value": target.isoformat(), "iso_date": target.isoformat()}

    if any(keyword in normalized for keyword in ("jutro", "jutrzejsz", "tomorrow")):
        target = date.today() + timedelta(days=1)
        return {"tool_value": "jutro", "iso_date": target.isoformat()}

    if any(keyword in normalized for keyword in ("wczoraj", "wczorajsz", "yesterday")):
        target = date.today() - timedelta(days=1)
        return {"tool_value": "wczoraj", "iso_date": target.isoformat()}

    if any(keyword in normalized for keyword in ("dzis", "dzisiaj", "today")):
        target = date.today()
        return {"tool_value": target.isoformat(), "iso_date": target.isoformat()}

    return None

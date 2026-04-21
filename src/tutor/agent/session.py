from __future__ import annotations

import asyncio
from dataclasses import dataclass
from queue import Queue
from threading import Thread
from typing import Any, Iterator, Literal, cast
from collections.abc import Awaitable, Callable

from langsmith import traceable
from strands import Agent

from .models import ChatStreamEvent


@dataclass
class AgentChatSession:
    """Stateful chat session around a Strands agent."""

    app: Agent
    thread_id: str = "teacher-cli"
    extract_tool_statuses: (
        Callable[
            [dict[str, Any], dict[str, str]],
            list[tuple[str, Literal["completed", "error"], str]],
        ]
        | None
    ) = None
    is_passthrough_tool: Callable[[str], bool] | None = None
    format_passthrough_tool_output: Callable[[str], str] | None = None

    def stream(self, user_input: str) -> Iterator[ChatStreamEvent]:
        if not user_input.strip():
            return

        if self.extract_tool_statuses is None:
            raise RuntimeError("extract_tool_statuses is not configured.")
        if self.is_passthrough_tool is None:
            raise RuntimeError("is_passthrough_tool is not configured.")
        if self.format_passthrough_tool_output is None:
            raise RuntimeError("format_passthrough_tool_output is not configured.")
        extract_tool_statuses = self.extract_tool_statuses
        is_passthrough_tool = self.is_passthrough_tool
        format_passthrough_tool_output = self.format_passthrough_tool_output

        prepared_input = user_input.strip()
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

                    for tool_name, status, summary in extract_tool_statuses(
                        event,
                        tool_names_by_use_id,
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
                            is_passthrough_tool(tool_name)
                            and status == "completed"
                            and isinstance(summary, str)
                            and not passthrough_emitted
                        ):
                            passthrough_emitted = True
                            stream_queue.put(
                                ChatStreamEvent(
                                    kind="tool_output",
                                    text=format_passthrough_tool_output(summary),
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
                aclose = getattr(async_stream, "aclose", None)
                if callable(aclose):
                    await cast(Callable[[], Awaitable[None]], aclose)()
                stream_queue.put(done_marker)

        worker = Thread(target=lambda: asyncio.run(_collect_events()), daemon=True)
        worker.start()

        while True:
            item = stream_queue.get()
            if item is done_marker:
                break
            if isinstance(item, Exception):
                raise item
            yield cast(ChatStreamEvent, item)

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

        result = self.app(user_input.strip())
        resolved = _extract_text_from_agent_result(result).strip()
        return resolved or "Gotowe."


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

"""LangGraph orchestration for interactive tutor assistant chat."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
import os
from typing import Annotated, Any, Iterator, Literal, TypedDict
from uuid import uuid4

from langchain_aws import ChatBedrockConverse
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, RemoveMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition

from .tools import AgentToolDefaults, create_agent_tools

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


class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]


@dataclass(frozen=True)
class ChatStreamEvent:
    """Single event produced while streaming an agent response."""

    kind: Literal["token", "tool", "tool_output"]
    text: str
    status: Literal["pending", "completed", "error"] | None = None
    summary: str | None = None


@dataclass
class AgentChatSession:
    """Stateful chat session around a compiled LangGraph app."""

    app: Any
    thread_id: str = "teacher-cli"

    def _reset_thread_state(self) -> None:
        config = {"configurable": {"thread_id": self.thread_id}}
        snapshot = self.app.get_state(config)
        current_messages = snapshot.values.get("messages", [])
        if not current_messages:
            return

        removals = [
            RemoveMessage(id=message.id)
            for message in current_messages
            if message.id is not None
        ]
        if not removals:
            return
        self.app.update_state(config, {"messages": removals})

    def stream(self, user_input: str) -> Iterator[ChatStreamEvent]:
        if not user_input.strip():
            return

        payload = {"messages": [HumanMessage(content=_prepare_user_input(user_input))]}
        config = {"configurable": {"thread_id": self.thread_id}}

        for attempt in range(3):
            seen_tool_calls: set[str] = set()
            try:
                stream = self.app.stream(
                    payload,
                    config=config,
                    stream_mode=["messages", "updates"],
                )
                for item in stream:
                    for mode, chunk in _normalize_stream_item(item):
                        if mode == "messages":
                            for tool_name in _extract_pending_tool_names(chunk):
                                key = f"{tool_name}:pending:None"
                                if key in seen_tool_calls:
                                    continue
                                seen_tool_calls.add(key)
                                yield ChatStreamEvent(
                                    kind="tool",
                                    text=tool_name,
                                    status="pending",
                                    summary=None,
                                )

                            token = _extract_message_token(chunk)
                            if token:
                                yield ChatStreamEvent(kind="token", text=token)
                            continue

                        if mode == "updates":
                            for tool_name, status, summary in _extract_tool_statuses(chunk):
                                key = f"{tool_name}:{status}:{summary}"
                                if key in seen_tool_calls:
                                    continue
                                seen_tool_calls.add(key)
                                yield ChatStreamEvent(
                                    kind="tool",
                                    text=tool_name,
                                    status=status,
                                    summary=summary,
                                )
                                if (
                                    _is_passthrough_tool(tool_name)
                                    and status == "completed"
                                    and isinstance(summary, str)
                                ):
                                    yield ChatStreamEvent(
                                        kind="tool_output",
                                        text=_format_passthrough_tool_output(summary),
                                    )
                                    return
                return
            except Exception as exc:  # noqa: BLE001
                details = str(exc)
                if "tool_use" not in details or "tool_result" not in details or attempt == 2:
                    raise

                if attempt == 0:
                    self._reset_thread_state()
                else:
                    self.thread_id = f"{self.thread_id}-recovered-{uuid4().hex[:8]}"
                config = {"configurable": {"thread_id": self.thread_id}}

    def ask(self, user_input: str) -> str:
        chunks: list[str] = []
        for event in self.stream(user_input):
            if event.kind in {"token", "tool_output"}:
                chunks.append(event.text)

        text = "".join(chunks).strip()
        if text:
            return text

        payload = {"messages": [HumanMessage(content=_prepare_user_input(user_input))]}
        config = {"configurable": {"thread_id": self.thread_id}}
        result = self.app.invoke(payload, config=config)

        messages = result.get("messages", [])
        for message in reversed(messages):
            if isinstance(message, AIMessage):
                text = message.text.strip()
                if text:
                    return text

        return "Gotowe."


def build_agent_app(*, defaults: AgentToolDefaults | None = None):
    tools = create_agent_tools(defaults=defaults)
    tool_node = ToolNode(tools)

    llm = ChatBedrockConverse(
        model=_resolve_agent_model_id(),
        region_name=_resolve_region_name(),
        temperature=0,
        max_tokens=1200,
        system=[SYSTEM_PROMPT],
    )
    llm_with_tools = llm.bind_tools(tools)

    def _call_model(state: AgentState) -> AgentState:
        response = llm_with_tools.invoke(state["messages"])
        return {"messages": [response]}

    graph = StateGraph(AgentState)
    graph.add_node("agent", _call_model)
    graph.add_node("tools", tool_node)
    graph.add_edge(START, "agent")
    graph.add_conditional_edges("agent", tools_condition)
    graph.add_edge("tools", "agent")

    return graph.compile(checkpointer=MemorySaver())


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


def _normalize_stream_item(item: Any) -> Iterator[tuple[str, Any]]:
    if isinstance(item, tuple) and len(item) == 2 and isinstance(item[0], str):
        yield item[0], item[1]
        return

    yield "messages", item


def _extract_message_token(chunk: Any) -> str:
    message = chunk
    metadata = None
    if isinstance(chunk, tuple) and len(chunk) == 2:
        message, metadata = chunk

    if isinstance(metadata, dict):
        node_name = metadata.get("langgraph_node")
        if isinstance(node_name, str) and node_name != "agent":
            return ""

    if _has_tool_call_payload(message):
        return ""

    return _extract_text_from_message(message)


def _has_tool_call_payload(message: Any) -> bool:
    tool_calls = getattr(message, "tool_calls", None)
    if isinstance(tool_calls, list) and tool_calls:
        return True

    tool_call_chunks = getattr(message, "tool_call_chunks", None)
    if isinstance(tool_call_chunks, list) and tool_call_chunks:
        return True

    return False


def _extract_text_from_message(message: Any) -> str:
    text = getattr(message, "text", None)
    if isinstance(text, str) and text:
        return text

    content = getattr(message, "content", None)
    return _extract_text_from_content(content)


def _extract_text_from_content(content: Any) -> str:
    if isinstance(content, str):
        return content

    if isinstance(content, list):
        fragments: list[str] = []
        for item in content:
            if isinstance(item, str):
                fragments.append(item)
            elif isinstance(item, dict):
                value = item.get("text")
                if isinstance(value, str):
                    fragments.append(value)
        return "".join(fragments)

    return ""


def _extract_pending_tool_names(chunk: Any) -> list[str]:
    if isinstance(chunk, tuple) and len(chunk) == 2:
        chunk = chunk[0]

    tool_names: list[str] = []

    tool_calls = getattr(chunk, "tool_calls", None)
    if isinstance(tool_calls, list):
        for tc in tool_calls:
            if not isinstance(tc, dict):
                continue
            name = tc.get("name")
            if isinstance(name, str) and name:
                tool_names.append(name)

    tool_call_chunks = getattr(chunk, "tool_call_chunks", None)
    if isinstance(tool_call_chunks, list):
        for tc in tool_call_chunks:
            if not isinstance(tc, dict):
                continue
            name = tc.get("name")
            if isinstance(name, str) and name:
                tool_names.append(name)

    return tool_names


def _extract_tool_statuses(
    chunk: Any,
) -> list[tuple[str, Literal["completed", "error"], str]]:
    if not isinstance(chunk, dict):
        return []

    tool_statuses: list[tuple[str, Literal["completed", "error"], str]] = []
    for update in chunk.values():
        if not isinstance(update, dict):
            continue

        messages = update.get("messages")
        if not isinstance(messages, list):
            continue

        for message in messages:
            tool_name = getattr(message, "name", None)
            if not isinstance(tool_name, str) or not tool_name:
                continue

            content = _extract_text_from_content(getattr(message, "content", None))
            status: Literal["completed", "error"]
            if "Wystapil blad podczas wykonania narzedzia" in content:
                status = "error"
            else:
                status = "completed"

            summary = _summarize_tool_content(content)
            if _is_passthrough_tool(tool_name) and status == "completed":
                summary = content

            tool_statuses.append((tool_name, status, summary))

    return tool_statuses


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

    if any(
        keyword in normalized
        for keyword in ("jutro", "jutrzejsz", "tomorrow")
    ):
        target = date.today() + timedelta(days=1)
        return {"tool_value": "jutro", "iso_date": target.isoformat()}

    if any(
        keyword in normalized
        for keyword in ("wczoraj", "wczorajsz", "yesterday")
    ):
        target = date.today() - timedelta(days=1)
        return {"tool_value": "wczoraj", "iso_date": target.isoformat()}

    if any(keyword in normalized for keyword in ("dzis", "dzisiaj", "today")):
        target = date.today()
        return {"tool_value": target.isoformat(), "iso_date": target.isoformat()}

    return None

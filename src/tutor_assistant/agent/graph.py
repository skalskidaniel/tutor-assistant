"""LangGraph orchestration for interactive tutor assistant chat."""

from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Annotated, Any, TypedDict
from uuid import uuid4

from langchain_aws import ChatBedrockConverse
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, RemoveMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition

from .tools import AgentToolDefaults, create_agent_tools

DEFAULT_AGENT_MODEL_ID = "anthropic.claude-3-haiku-20240307-v1:0"
SYSTEM_PROMPT = (
    "Jestes asystentem nauczyciela matematyki. "
    "Rozmawiaj po polsku i odpowiadaj zwiezle. "
    "Nigdy nie tworz placeholderow dat typu WSTAW_... i podobnych. "
    "Gdy prosba wymaga dzialania na Google Calendar/Drive/Gmail, "
    "uzywaj dostepnych narzedzi zamiast zgadywac wynik."
)


class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]


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

    def ask(self, user_input: str) -> str:
        if not user_input.strip():
            return ""

        payload = {"messages": [HumanMessage(content=user_input)]}
        config = {"configurable": {"thread_id": self.thread_id}}
        try:
            result = self.app.invoke(payload, config=config)
        except Exception as exc:  # noqa: BLE001
            details = str(exc)
            if "tool_use" in details and "tool_result" in details:
                self._reset_thread_state()
                try:
                    result = self.app.invoke(payload, config=config)
                except Exception:
                    self.thread_id = f"{self.thread_id}-recovered-{uuid4().hex[:8]}"
                    recovery_config = {"configurable": {"thread_id": self.thread_id}}
                    result = self.app.invoke(payload, config=recovery_config)
            else:
                raise

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
        model_id=_resolve_agent_model_id(),
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


def _resolve_agent_model_id() -> str:
    return os.getenv(
        "BEDROCK_AGENT_MODEL_ID",
        os.getenv("BEDROCK_MODEL_ID", DEFAULT_AGENT_MODEL_ID),
    )


def _resolve_region_name() -> str:
    return os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION", "eu-central-1")

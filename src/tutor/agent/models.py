from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class ChatStreamEvent:
    """Single event produced while streaming an agent response."""

    kind: Literal["token", "tool", "tool_output"]
    text: str
    status: Literal["pending", "completed", "error"] | None = None
    summary: str | None = None

@dataclass
class ThinkingStreamState:
    """State of the thinking stream."""
    inside_thinking: bool = False
    carry: str = ""
    pending_strip_visible_leading_newlines: bool = False
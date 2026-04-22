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

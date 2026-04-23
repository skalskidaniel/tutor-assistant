from __future__ import annotations


class ThinkingStreamParser:

    def __init__(self) -> None:
        self._inside_thinking = False
        self._carry = ""
        self._pending_strip_visible_leading_newlines = True

    @property
    def inside_thinking(self) -> bool:
        return self._inside_thinking

    @property
    def pending_strip_visible_leading_newlines(self) -> bool:
        return self._pending_strip_visible_leading_newlines

    def mark_pending_visible_newline_strip(self) -> None:
        self._pending_strip_visible_leading_newlines = True

    def consume(self, chunk: str) -> tuple[str, str]:
        open_tag = "<thinking>"
        close_tag = "</thinking>"
        combined = self._carry + chunk
        self._carry = ""
        visible_parts: list[str] = []
        reasoning_parts: list[str] = []

        while combined:
            if self._inside_thinking:
                close_index = combined.find(close_tag)
                if close_index == -1:
                    keep = len(close_tag) - 1
                    if len(combined) > keep:
                        reasoning_parts.append(combined[:-keep])
                        self._carry = combined[-keep:]
                    else:
                        self._carry = combined
                    break

                reasoning_parts.append(combined[:close_index])
                combined = combined[close_index + len(close_tag) :]
                self._inside_thinking = False
                self._pending_strip_visible_leading_newlines = True
                continue

            open_index = combined.find(open_tag)
            if open_index == -1:
                keep = len(open_tag) - 1
                if len(combined) > keep:
                    visible_parts.append(combined[:-keep])
                    self._carry = combined[-keep:]
                else:
                    self._carry = combined
                break

            visible_parts.append(combined[:open_index])
            combined = combined[open_index + len(open_tag) :]
            self._inside_thinking = True

        return "".join(visible_parts), "".join(reasoning_parts)

    def apply_pending_visible_leading_newline_strip(self, visible_text: str) -> str:
        if not self._pending_strip_visible_leading_newlines:
            return visible_text
        stripped = visible_text.lstrip("\n\r ")
        if stripped:
            self._pending_strip_visible_leading_newlines = False
        return stripped

    def flush(self) -> tuple[str, str]:
        if not self._carry:
            return "", ""

        tail = self._carry
        self._carry = ""
        if self._inside_thinking:
            return "", tail
        return tail, ""

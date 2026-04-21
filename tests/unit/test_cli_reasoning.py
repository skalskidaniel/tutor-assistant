from tutor.agent.cli import (  # pyright: ignore[reportMissingImports]
    _ThinkingStreamState,
    _apply_pending_visible_leading_newline_strip,
    _flush_thinking_state,
    _split_thinking_chunks,
)


def test_split_thinking_chunks_hides_reasoning_from_visible_output() -> None:
    state = _ThinkingStreamState()

    visible, reasoning = _split_thinking_chunks(
        "Czesc<thinking>wewnetrzne notatki</thinking> swiat", state
    )
    tail_visible, tail_reasoning = _flush_thinking_state(state)

    assert visible + tail_visible == "Czesc swiat"
    assert reasoning == "wewnetrzne notatki"
    assert tail_reasoning == ""
    assert state.inside_thinking is False


def test_split_thinking_chunks_handles_fragmented_tags_across_tokens() -> None:
    state = _ThinkingStreamState()

    parts = [
        "Ala<thi",
        "nking>sekret",
        "owy tok</thin",
        "king> ma kota",
    ]
    visible_chunks: list[str] = []
    reasoning_chunks: list[str] = []

    for part in parts:
        visible, reasoning = _split_thinking_chunks(part, state)
        visible_chunks.append(visible)
        reasoning_chunks.append(reasoning)

    tail_visible, tail_reasoning = _flush_thinking_state(state)
    visible_chunks.append(tail_visible)
    reasoning_chunks.append(tail_reasoning)

    assert "".join(visible_chunks) == "Ala ma kota"
    assert "".join(reasoning_chunks) == "sekretowy tok"


def test_flush_thinking_state_returns_reasoning_tail_when_unclosed() -> None:
    state = _ThinkingStreamState(inside_thinking=True, carry="niedomkniety")

    visible, reasoning = _flush_thinking_state(state)

    assert visible == ""
    assert reasoning == "niedomkniety"


def test_split_thinking_sets_pending_strip_after_close_tag() -> None:
    state = _ThinkingStreamState()
    _split_thinking_chunks("<thinking>a</thinking>", state)

    assert state.pending_strip_visible_leading_newlines is True
    assert state.inside_thinking is False


def test_apply_pending_visible_leading_newline_strip_strips_across_chunks() -> None:
    state = _ThinkingStreamState(pending_strip_visible_leading_newlines=True)

    assert _apply_pending_visible_leading_newline_strip("\n", state) == ""
    assert state.pending_strip_visible_leading_newlines is True

    assert _apply_pending_visible_leading_newline_strip("\n\n", state) == ""
    assert state.pending_strip_visible_leading_newlines is True

    assert (
        _apply_pending_visible_leading_newline_strip("Odpowiedz", state)
        == "Odpowiedz"
    )
    assert state.pending_strip_visible_leading_newlines is False


def test_apply_pending_visible_leading_newline_strip_noop_when_not_pending() -> None:
    state = _ThinkingStreamState()
    text = "\n\nWidoczna linia"

    assert _apply_pending_visible_leading_newline_strip(text, state) == text

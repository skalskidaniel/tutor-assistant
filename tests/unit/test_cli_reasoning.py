from tutor.agent.stream_parser import ThinkingStreamParser


def test_split_thinking_chunks_hides_reasoning_from_visible_output() -> None:
    parser = ThinkingStreamParser()

    visible, reasoning = parser.consume(
        "Czesc<thinking>wewnetrzne notatki</thinking> swiat"
    )
    tail_visible, tail_reasoning = parser.flush()

    assert visible + tail_visible == "Czesc swiat"
    assert reasoning == "wewnetrzne notatki"
    assert tail_reasoning == ""
    assert parser.inside_thinking is False


def test_split_thinking_chunks_handles_fragmented_tags_across_tokens() -> None:
    parser = ThinkingStreamParser()

    parts = [
        "Ala<thi",
        "nking>sekret",
        "owy tok</thin",
        "king> ma kota",
    ]
    visible_chunks: list[str] = []
    reasoning_chunks: list[str] = []

    for part in parts:
        visible, reasoning = parser.consume(part)
        visible_chunks.append(visible)
        reasoning_chunks.append(reasoning)

    tail_visible, tail_reasoning = parser.flush()
    visible_chunks.append(tail_visible)
    reasoning_chunks.append(tail_reasoning)

    assert "".join(visible_chunks) == "Ala ma kota"
    assert "".join(reasoning_chunks) == "sekretowy tok"


def test_flush_thinking_state_returns_reasoning_tail_when_unclosed() -> None:
    parser = ThinkingStreamParser()
    _, emitted_reasoning = parser.consume("<thinking>niedomkniety")

    visible, reasoning = parser.flush()

    assert visible == ""
    assert emitted_reasoning + reasoning == "niedomkniety"


def test_split_thinking_sets_pending_strip_after_close_tag() -> None:
    parser = ThinkingStreamParser()
    parser.consume("<thinking>a</thinking>")

    assert parser.pending_strip_visible_leading_newlines is True
    assert parser.inside_thinking is False


def test_apply_pending_visible_leading_newline_strip_strips_across_chunks() -> None:
    parser = ThinkingStreamParser()

    assert parser.apply_pending_visible_leading_newline_strip("\n") == ""
    assert parser.pending_strip_visible_leading_newlines is True

    assert parser.apply_pending_visible_leading_newline_strip("\n\n") == ""
    assert parser.pending_strip_visible_leading_newlines is True

    assert (
        parser.apply_pending_visible_leading_newline_strip("Odpowiedz") == "Odpowiedz"
    )
    assert parser.pending_strip_visible_leading_newlines is False


def test_apply_pending_visible_leading_newline_strip_noop_when_not_pending() -> None:
    parser = ThinkingStreamParser()
    text = "\n\nWidoczna linia"

    parser.apply_pending_visible_leading_newline_strip("Pierwsza odpowiedz")
    assert parser.apply_pending_visible_leading_newline_strip(text) == text

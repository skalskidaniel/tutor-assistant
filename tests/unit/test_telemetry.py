from pathlib import Path
from types import SimpleNamespace
import json

import tutor.core.telemetry as telemetry


def test_setup_telemetry_creates_log_directory_and_files(monkeypatch, tmp_path: Path) -> None:
    log_dir = tmp_path / ".logs"
    monkeypatch.setenv("TUTOR_LOG_DIR", str(log_dir))
    monkeypatch.setenv("TUTOR_LOG_LEVEL", "DEBUG")

    telemetry._close_trace_log_stream()
    telemetry._is_initialized = False

    telemetry.setup_telemetry()

    assert log_dir.exists()
    assert (log_dir / "tutor-assistant.log").exists()
    assert (log_dir / "strands-telemetry.log").exists()

    telemetry._close_trace_log_stream()
    telemetry._is_initialized = False


def test_format_span_json_utf8_keeps_polish_characters() -> None:
    payload = {"name": "Zażółć gęślą jaźń"}
    span = SimpleNamespace(to_json=lambda: json.dumps(payload, ensure_ascii=True))

    output = telemetry._format_span_json_utf8(span)

    assert "Zażółć gęślą jaźń" in output
    assert "\\u017c" not in output

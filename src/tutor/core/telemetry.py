from __future__ import annotations

import atexit
import json
import logging
import os
from dataclasses import dataclass
from logging.handlers import RotatingFileHandler
from pathlib import Path
from threading import Lock
from typing import Any, TextIO

from strands.telemetry import StrandsTelemetry

_DEFAULT_LOG_LEVEL = "INFO"
_DEFAULT_LOG_DIR = ".logs"
_APP_LOG_FILE = "tutor-assistant.log"
_TRACE_LOG_FILE = "strands-telemetry.log"
_LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"

_setup_lock = Lock()
_is_initialized = False
_trace_log_stream: TextIO | None = None


@dataclass(frozen=True)
class TelemetrySettings:
    log_level: int
    log_dir: Path

    @property
    def app_log_path(self) -> Path:
        return self.log_dir / _APP_LOG_FILE

    @property
    def trace_log_path(self) -> Path:
        return self.log_dir / _TRACE_LOG_FILE


def setup_telemetry() -> None:
    global _is_initialized

    with _setup_lock:
        if _is_initialized:
            return

        settings = _resolve_settings()
        settings.log_dir.mkdir(parents=True, exist_ok=True)

        _configure_python_logging(settings)

        telemetry = StrandsTelemetry()
        telemetry.setup_console_exporter(
            out=_open_trace_log_stream(settings.trace_log_path),
            formatter=_format_span_json_utf8,
        )

        logging.getLogger(__name__).info(
            "Telemetry initialized (log_dir=%s)",
            settings.log_dir,
        )
        _is_initialized = True


def _resolve_settings() -> TelemetrySettings:
    level_name = os.getenv("TUTOR_LOG_LEVEL", _DEFAULT_LOG_LEVEL).strip().upper() or _DEFAULT_LOG_LEVEL
    level = _parse_log_level(level_name)

    log_dir_raw = os.getenv("TUTOR_LOG_DIR", _DEFAULT_LOG_DIR).strip() or _DEFAULT_LOG_DIR
    log_dir = Path(log_dir_raw)

    return TelemetrySettings(log_level=level, log_dir=log_dir)


def _parse_log_level(level_name: str) -> int:
    level = logging.getLevelName(level_name)
    if isinstance(level, int):
        return level
    return logging.INFO


def _configure_python_logging(settings: TelemetrySettings) -> None:
    file_handler = RotatingFileHandler(
        settings.app_log_path,
        maxBytes=2 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    logging.basicConfig(
        level=settings.log_level,
        format=_LOG_FORMAT,
        handlers=[file_handler],
        force=True,
    )


def _open_trace_log_stream(log_path: Path) -> TextIO:
    global _trace_log_stream

    if _trace_log_stream is None or _trace_log_stream.closed:
        _trace_log_stream = log_path.open("a", encoding="utf-8")
        atexit.register(_close_trace_log_stream)
    return _trace_log_stream


def _format_span_json_utf8(span: Any) -> str:
    raw_json = span.to_json()
    payload = json.loads(raw_json)
    return json.dumps(payload, ensure_ascii=False, indent=4) + os.linesep


def _close_trace_log_stream() -> None:
    global _trace_log_stream

    if _trace_log_stream is None:
        return
    if not _trace_log_stream.closed:
        _trace_log_stream.close()
    _trace_log_stream = None

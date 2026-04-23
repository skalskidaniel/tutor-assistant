from __future__ import annotations

import os
import unicodedata
from pathlib import Path
from typing import cast

from googleapiclient.errors import HttpError


def slugify(value: str) -> str:
    normalized = value.lower().strip()
    normalized = normalized.replace("ł", "l")
    normalized = "".join(
        char
        for char in unicodedata.normalize("NFKD", normalized)
        if not unicodedata.combining(char)
    )

    result: list[str] = []
    previous_dash = False
    for char in normalized:
        if char.isalnum():
            result.append(char)
            previous_dash = False
        elif not previous_dash:
            result.append("-")
            previous_dash = True

    slug = "".join(result).strip("-")
    return slug or "uczeń"

def resolve_required_path(
    *, explicit_path: str | Path | None, env_var_name: str
) -> Path:
    env_value = os.getenv(env_var_name)
    if env_value:
        return Path(env_value)

    if explicit_path is not None:
        return Path(explicit_path)

    raise ValueError(
        f"Did not resolve the path. Set {env_var_name}."
    )

def extract_bedrock_text(payload: object) -> str:
    if not isinstance(payload, dict):
        raise RuntimeError("Bedrock returned unexpected response.")

    content_candidates: list[object] = []
    content_candidates.append(payload.get("content"))

    output = payload.get("output")
    if isinstance(output, dict):
        message = output.get("message")
        if isinstance(message, dict):
            content_candidates.append(message.get("content"))

    for candidate in content_candidates:
        if not isinstance(candidate, list):
            continue
        content = cast(list[object], candidate)
        for block in content:
            if not isinstance(block, dict):
                continue
            text = block.get("text")
            if isinstance(text, str) and text.strip():
                return text

    raise RuntimeError(
        "AWS Bedrock response does not contain text content "
        "in 'content' or 'output.message.content'."
    )

def format_http_error(error: HttpError) -> str:
    status = getattr(error.resp, "status", "unknown")
    reason = getattr(error, "reason", None)
    if isinstance(reason, str) and reason:
        return f"HTTP {status}: {reason}"
    return f"HTTP {status}: {error}"
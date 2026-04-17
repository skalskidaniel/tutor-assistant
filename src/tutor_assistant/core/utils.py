"""Shared utility functions."""

from __future__ import annotations

import unicodedata


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
    return slug or "uczen"

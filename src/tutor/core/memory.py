from __future__ import annotations

import json
import os
from pathlib import Path

DEFAULT_MEMORY_FILE_NAME = ".agent_memory.json"
DEFAULT_MEMORY_NAMESPACE = "teacher-cli"


class MemoryService:
    """Simple JSON-backed key-value memory for chat agent sessions."""

    def __init__(self, *, memory_path: str | Path | None = DEFAULT_MEMORY_FILE_NAME) -> None:
        env_memory_path = os.getenv("TUTOR_AGENT_MEMORY_PATH")
        if memory_path == DEFAULT_MEMORY_FILE_NAME and env_memory_path:
            self._memory_path = Path(env_memory_path)
            return

        if memory_path is None:
            self._memory_path = Path(env_memory_path or DEFAULT_MEMORY_FILE_NAME)
            return

        self._memory_path = Path(memory_path)

    @property
    def memory_path(self) -> Path:
        return self._memory_path

    def get_all(self, *, namespace: str = DEFAULT_MEMORY_NAMESPACE) -> dict[str, str]:
        payload = self._read_payload()
        namespaces = payload.get("namespaces")
        if not isinstance(namespaces, dict):
            return {}

        namespace_data = namespaces.get(namespace)
        if not isinstance(namespace_data, dict):
            return {}

        resolved: dict[str, str] = {}
        for key, value in namespace_data.items():
            if isinstance(key, str) and isinstance(value, str):
                resolved[key] = value
        return resolved

    def get(self, *, namespace: str = DEFAULT_MEMORY_NAMESPACE, key: str) -> str | None:
        values = self.get_all(namespace=namespace)
        return values.get(key)

    def set(self, *, namespace: str = DEFAULT_MEMORY_NAMESPACE, key: str, value: str) -> None:
        normalized_key = key.strip()
        normalized_value = value.strip()
        if not normalized_key:
            raise ValueError("Memory key cannot be empty.")
        if not normalized_value:
            raise ValueError("Memory value cannot be empty.")

        payload = self._read_payload()
        namespaces = payload.setdefault("namespaces", {})
        if not isinstance(namespaces, dict):
            namespaces = {}
            payload["namespaces"] = namespaces

        namespace_data = namespaces.setdefault(namespace, {})
        if not isinstance(namespace_data, dict):
            namespace_data = {}
            namespaces[namespace] = namespace_data

        namespace_data[normalized_key] = normalized_value
        self._write_payload(payload)

    def set_many(
        self,
        *,
        namespace: str = DEFAULT_MEMORY_NAMESPACE,
        values: dict[str, str],
    ) -> None:
        for key, value in values.items():
            self.set(namespace=namespace, key=key, value=value)

    def delete(self, *, namespace: str = DEFAULT_MEMORY_NAMESPACE, key: str) -> bool:
        payload = self._read_payload()
        namespaces = payload.get("namespaces")
        if not isinstance(namespaces, dict):
            return False

        namespace_data = namespaces.get(namespace)
        if not isinstance(namespace_data, dict):
            return False

        if key not in namespace_data:
            return False

        del namespace_data[key]
        self._write_payload(payload)
        return True

    def _read_payload(self) -> dict[str, object]:
        if not self._memory_path.exists():
            return {"version": 1, "namespaces": {}}

        try:
            raw = self._memory_path.read_text(encoding="utf-8")
            parsed = json.loads(raw)
        except Exception:
            return {"version": 1, "namespaces": {}}

        if not isinstance(parsed, dict):
            return {"version": 1, "namespaces": {}}

        if "version" not in parsed:
            parsed["version"] = 1
        if "namespaces" not in parsed or not isinstance(parsed["namespaces"], dict):
            parsed["namespaces"] = {}
        return parsed

    def _write_payload(self, payload: dict[str, object]) -> None:
        parent = self._memory_path.parent
        if parent and parent != Path(""):
            parent.mkdir(parents=True, exist_ok=True)

        self._memory_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

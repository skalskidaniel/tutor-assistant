from typing import Callable

from tutor_assistant.core.memory import DEFAULT_MEMORY_NAMESPACE, MemoryService

from .common import agent_tool, tool_error_message


def make_memory_tools(
    *, memory_service: MemoryService, namespace: str = DEFAULT_MEMORY_NAMESPACE
) -> list[Callable[..., object]]:
    @agent_tool
    def save_to_memory(key: str, value: str) -> str:
        """Zapisuje trwala informacje konfiguracyjna lub preferencje uzytkownika."""
        try:
            memory_service.set(namespace=namespace, key=key, value=value)
            return f"Zapisano w pamieci: {key}"
        except Exception as exc:  # noqa: BLE001
            return tool_error_message(exc)

    @agent_tool
    def delete_from_memory(key: str) -> str:
        """Usuwa klucz z trwalej pamieci agenta."""
        try:
            deleted = memory_service.delete(namespace=namespace, key=key)
            if deleted:
                return f"Usunieto z pamieci: {key}"
            return f"Brak klucza w pamieci: {key}"
        except Exception as exc:  # noqa: BLE001
            return tool_error_message(exc)

    @agent_tool
    def read_memory() -> str:
        """Zwraca zapisane preferencje i konfiguracje uzytkownika."""
        try:
            entries = memory_service.get_all(namespace=namespace)
            if not entries:
                return "Pamiec jest pusta."

            lines = ["Zapamietane informacje:"]
            for key in sorted(entries):
                lines.append(f"- {key}: {entries[key]}")
            return "\n".join(lines)
        except Exception as exc:  # noqa: BLE001
            return tool_error_message(exc)

    return [save_to_memory, delete_from_memory, read_memory]

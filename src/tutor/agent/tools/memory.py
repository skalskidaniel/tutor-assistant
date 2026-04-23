from typing import Callable

from tutor.core.memory import DEFAULT_MEMORY_NAMESPACE, MemoryService

from .common import agent_tool


def make_memory_tools(
    *, memory_service: MemoryService, namespace: str = DEFAULT_MEMORY_NAMESPACE
) -> list[Callable[..., object]]:
    @agent_tool
    def save_to_memory(key: str, value: str) -> str:
        """Zapisuje trwale informacje konfiguracyjne lub preferencje użytkownika."""
        memory_service.set(namespace=namespace, key=key, value=value)
        return f"Zapisano w pamięci: {key}"

    @agent_tool
    def delete_from_memory(key: str) -> str:
        """Usuwa klucz z trwałej pamięci agenta."""
        deleted = memory_service.delete(namespace=namespace, key=key)
        if deleted:
            return f"Usunięto z pamięci: {key}"
        return f"Brak klucza w pamięci: {key}"

    @agent_tool
    def read_memory() -> str:
        """Zwraca zapisane preferencje i konfiguracje użytkownika."""
        entries = memory_service.get_all(namespace=namespace)
        if not entries:
            return "Pamięć jest pusta."

        lines = ["Zapamiętane informacje:"]
        for key in sorted(entries):
            lines.append(f"- {key}: {entries[key]}")
        return "\n".join(lines)

    return [save_to_memory, delete_from_memory, read_memory]

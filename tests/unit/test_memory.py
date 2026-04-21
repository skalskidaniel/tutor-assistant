from pathlib import Path

from tutor.core.memory import DEFAULT_MEMORY_NAMESPACE, MemoryService


def test_memory_service_persists_values_by_namespace(tmp_path: Path) -> None:
    memory_path = tmp_path / "memory.json"
    service = MemoryService(memory_path=memory_path)

    service.set(namespace="session-a", key="calendar_id", value="primary")
    service.set(namespace="session-b", key="calendar_id", value="team@group.calendar")

    assert service.get(namespace="session-a", key="calendar_id") == "primary"
    assert service.get(namespace="session-b", key="calendar_id") == "team@group.calendar"


def test_memory_service_delete_returns_expected_flag(tmp_path: Path) -> None:
    memory_path = tmp_path / "memory.json"
    service = MemoryService(memory_path=memory_path)
    service.set(namespace=DEFAULT_MEMORY_NAMESPACE, key="reply_style", value="krotko")

    assert service.delete(namespace=DEFAULT_MEMORY_NAMESPACE, key="reply_style") is True
    assert service.delete(namespace=DEFAULT_MEMORY_NAMESPACE, key="reply_style") is False

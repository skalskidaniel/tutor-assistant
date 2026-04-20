from pathlib import Path

from tutor_assistant.core.auth import (  # pyright: ignore[reportMissingImports]
    ensure_google_credentials_file,
)


def test_ensure_google_credentials_file_creates_from_env(
    monkeypatch,
    tmp_path: Path,
) -> None:
    credentials_path = tmp_path / "credentials.json"
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_ID", "client-id-123")
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_SECRET", "secret-456")
    monkeypatch.setenv("GOOGLE_OAUTH_PROJECT_ID", "proj-1")

    created = ensure_google_credentials_file(credentials_path=credentials_path)

    assert created is True
    assert credentials_path.exists()
    content = credentials_path.read_text(encoding="utf-8")
    assert '"client_id": "client-id-123"' in content
    assert '"client_secret": "secret-456"' in content


def test_ensure_google_credentials_file_returns_false_when_env_missing(
    monkeypatch,
    tmp_path: Path,
) -> None:
    credentials_path = tmp_path / "credentials.json"
    monkeypatch.delenv("GOOGLE_OAUTH_CLIENT_ID", raising=False)
    monkeypatch.delenv("GOOGLE_OAUTH_CLIENT_SECRET", raising=False)

    created = ensure_google_credentials_file(credentials_path=credentials_path)

    assert created is False
    assert not credentials_path.exists()

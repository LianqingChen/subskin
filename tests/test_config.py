from __future__ import annotations

import pytest

from src.config import Settings, ValidationError, settings


def test_settings_loads_values_from_env_file(tmp_path, monkeypatch) -> None:
    for name in (
        "OPENAI_API_KEY",
        "SCHEDULER_ENABLED",
        "TRACK_INCREMENTAL_UPDATES",
        "UPDATE_RETRY_ATTEMPTS",
        "WORKER_PROCESSES",
        "SITE_URL",
        "QQ_BOT_API_URL",
    ):
        monkeypatch.delenv(name, raising=False)

    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "OPENAI_API_KEY=sk-test",
                "SCHEDULER_ENABLED=0",
                "TRACK_INCREMENTAL_UPDATES=1",
                "UPDATE_RETRY_ATTEMPTS=5",
                "WORKER_PROCESSES=8",
                "SITE_URL=https://example.org",
                "QQ_BOT_API_URL=http://localhost:8081",
            ]
        ),
        encoding="utf-8",
    )

    config = Settings.from_env_file(env_file)

    assert config.OPENAI_API_KEY == "sk-test"
    assert config.SCHEDULER_ENABLED is False
    assert config.TRACK_INCREMENTAL_UPDATES is True
    assert config.UPDATE_RETRY_ATTEMPTS == 5
    assert config.WORKER_PROCESSES == 8
    assert str(config.SITE_URL) == "https://example.org/"
    assert str(config.QQ_BOT_API_URL) == "http://localhost:8081/"


def test_settings_rejects_invalid_values(tmp_path, monkeypatch) -> None:
    for name in ("SITE_URL", "HEALTH_CHECK_PORT"):
        monkeypatch.delenv(name, raising=False)

    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "SITE_URL=not-a-url",
                "HEALTH_CHECK_PORT=70000",
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValidationError):
        Settings.from_env_file(env_file)


def test_module_singleton_is_available() -> None:
    assert settings is not None
    assert isinstance(settings, Settings)

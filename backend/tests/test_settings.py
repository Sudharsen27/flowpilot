from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from app.core import config as config_module
from app.core.config import Settings, default_env_files


def _settings(**kwargs: Any) -> Settings:
    """Build Settings without reading a developer .env file."""
    return Settings(environment="test", _env_file=None, **kwargs)


def test_ai_provider_defaults_to_openai() -> None:
    configured = _settings()
    assert configured.ai_provider == "openai"
    assert configured.openai_model == "gpt-4o-mini"
    assert configured.openai_api_key is None


def test_ai_provider_accepts_groq() -> None:
    configured = _settings(ai_provider="groq")
    assert configured.ai_provider == "groq"


def test_groq_model_default() -> None:
    configured = _settings()
    assert configured.groq_model == "openai/gpt-oss-20b"
    assert configured.groq_api_key is None


def test_groq_model_custom_value_is_accepted() -> None:
    configured = _settings(groq_model="openai/gpt-oss-120b")
    assert configured.groq_model == "openai/gpt-oss-120b"


def test_empty_groq_api_key_parses() -> None:
    configured = _settings(groq_api_key="")
    assert configured.groq_api_key == ""
    assert configured.ai_provider == "openai"


def test_invalid_ai_provider_is_rejected() -> None:
    with pytest.raises(ValidationError):
        _settings(ai_provider="anthropic")


def test_openai_only_env_remains_valid_without_groq_vars() -> None:
    configured = _settings(
        openai_api_key="sk-test-not-a-real-key",
        openai_model="gpt-4o-mini",
    )
    assert configured.ai_provider == "openai"
    assert configured.openai_api_key == "sk-test-not-a-real-key"
    assert configured.openai_model == "gpt-4o-mini"
    assert configured.groq_api_key is None
    assert configured.groq_model == "openai/gpt-oss-20b"
    assert configured.openai_request_timeout_seconds == 60


def test_default_env_files_are_absolute_and_cwd_independent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    files = default_env_files()
    assert len(files) == 2
    assert all(path.is_absolute() for path in files)
    assert files[0] == config_module._REPO_ROOT / ".env"
    assert files[1] == config_module._BACKEND_DIR / ".env"
    monkeypatch.chdir(tmp_path)
    assert default_env_files() == files


def test_settings_loads_env_file_when_cwd_differs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env_path = tmp_path / "project" / ".env"
    env_path.parent.mkdir()
    env_path.write_text(
        "\n".join(
            [
                "ENVIRONMENT=test",
                "AI_PROVIDER=groq",
                "GROQ_API_KEY=gsk_test_fake_not_real",
                "GROQ_MODEL=openai/gpt-oss-20b",
                "",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    configured = Settings(_env_file=env_path, _env_file_encoding="utf-8")
    assert configured.ai_provider == "groq"
    assert configured.groq_api_key == "gsk_test_fake_not_real"
    assert configured.groq_model == "openai/gpt-oss-20b"


PRODUCTION_SECRET = "production-secret-value-with-32-chars"


def _production(**kwargs: Any) -> Settings:
    values: dict[str, Any] = {
        "environment": "production",
        "secret_key": PRODUCTION_SECRET,
        "database_url": "postgresql+psycopg://db.internal:5432/app",
        "cors_origins": "https://app.example.com",
    }
    values.update(kwargs)
    return Settings(_env_file=None, **values)


def test_production_accepts_explicit_configuration() -> None:
    configured = _production(ai_provider="groq", groq_api_key=None)
    assert configured.is_production is True
    assert configured.cors_allow_origin_regex is None
    assert configured.cors_origin_list == ["https://app.example.com"]
    assert configured.groq_api_key is None


def test_production_rejects_default_secret() -> None:
    with pytest.raises(ValidationError, match="SECRET_KEY"):
        Settings(
            environment="production",
            database_url="postgresql+psycopg://db.internal:5432/app",
            cors_origins="https://app.example.com",
            _env_file=None,
        )


def test_production_rejects_local_database() -> None:
    with pytest.raises(ValidationError, match="DATABASE_URL"):
        _production(database_url="postgresql+psycopg://app:app@localhost:5432/app")


def test_production_rejects_localhost_and_wildcard_cors() -> None:
    with pytest.raises(ValidationError, match="CORS_ORIGINS"):
        _production(cors_origins="http://localhost:3000")
    with pytest.raises(ValidationError, match="CORS_ORIGINS"):
        _production(cors_origins="*")
    with pytest.raises(ValidationError, match="CORS_ORIGINS"):
        _production(cors_origins="")


def test_development_keeps_local_defaults() -> None:
    configured = Settings(environment="development", _env_file=None)
    assert configured.secret_key == "replace-with-a-long-random-local-secret"
    assert "localhost" in configured.cors_origins


def test_process_env_overrides_env_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text(
        "ENVIRONMENT=test\nAI_PROVIDER=groq\nGROQ_MODEL=from-file\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("AI_PROVIDER", "openai")
    monkeypatch.setenv("GROQ_MODEL", "from-process-env")
    configured = Settings(_env_file=env_path, _env_file_encoding="utf-8")
    assert configured.ai_provider == "openai"
    assert configured.groq_model == "from-process-env"

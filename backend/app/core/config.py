from pathlib import Path
from typing import Literal, Self

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

INSECURE_DEFAULT_SECRET = "replace-with-a-long-random-local-secret"

AiProviderName = Literal["openai", "groq"]

# Resolve .env from this file's location so loading does not depend on the
# process cwd (uvicorn may be started from repo root or backend/).
_BACKEND_DIR = Path(__file__).resolve().parents[2]
_REPO_ROOT = Path(__file__).resolve().parents[3]


def default_env_files() -> tuple[Path, ...]:
    """Repo-root .env first, then backend/.env. Missing files are ignored."""
    return (_REPO_ROOT / ".env", _BACKEND_DIR / ".env")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=default_env_files(),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "FlowPilot"
    environment: str = "development"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    database_url: str = "postgresql+psycopg://app:app@localhost:5432/app"
    redis_url: str = "redis://localhost:6379/0"
    cors_origins: str = "http://localhost:3000,http://localhost:3001"
    secret_key: str = INSECURE_DEFAULT_SECRET
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    # Selects which AIProvider implementation the factory will construct (Step 3).
    # Default keeps existing OpenAI-only deployments working without new env vars.
    ai_provider: AiProviderName = "openai"
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"
    # Shared AI request timeout for OpenAIProvider today; GroqProvider (Step 3)
    # should reuse this field rather than adding a second timeout setting.
    openai_request_timeout_seconds: float = 60
    groq_api_key: str | None = None
    groq_model: str = "openai/gpt-oss-20b"
    email_provider: str = "resend"
    resend_api_key: str | None = None
    email_from_address: str | None = None
    email_from_name: str | None = None
    email_request_timeout_seconds: float = 30
    agent_max_tool_iterations: int = 3
    # RUNNING rows older than this (and the provider-loop floor) may be recovered
    # as FAILED. Must stay large enough that a legitimate in-process run is not
    # treated as abandoned. There is no per-execution heartbeat.
    agent_execution_stale_timeout_seconds: float = Field(default=300, ge=1)
    lead_follow_up_execution_stale_timeout_seconds: float = Field(default=300, ge=1)
    # RUNNING sales runs older than this (and two provider-call floors) may be
    # recovered as FAILED. Qualification and drafting each call the provider.
    sales_run_stale_timeout_seconds: float = Field(default=300, ge=1)
    # The follow-up worker is a separate process (`python -m app.worker`). It is
    # never started by the API process, so this flag only guards that entrypoint.
    follow_up_worker_enabled: bool = False
    follow_up_worker_poll_interval_seconds: float = Field(default=30, ge=1)
    follow_up_worker_batch_size: int = Field(default=10, ge=1, le=50)
    # The Sales Agent auto-start worker shares `python -m app.worker`. It is
    # never started by the API process. Disabled by default so a local API
    # server never calls the model for website enquiries unexpectedly.
    sales_agent_auto_start_worker_enabled: bool = False
    sales_agent_auto_start_worker_poll_interval_seconds: float = Field(default=30, ge=1)
    sales_agent_auto_start_worker_batch_size: int = Field(default=10, ge=1, le=50)
    # In-process sliding window for public website capture. Single-instance only;
    # it is not shared across API processes and does not use Redis.
    website_capture_rate_limit_max: int = Field(default=5, ge=1)
    website_capture_rate_limit_window_seconds: float = Field(default=60, ge=1)

    def agent_execution_stale_timeout_effective_seconds(self) -> float:
        floor = (self.agent_max_tool_iterations + 1) * self.openai_request_timeout_seconds
        return max(self.agent_execution_stale_timeout_seconds, floor)

    def lead_follow_up_execution_stale_timeout_effective_seconds(self) -> float:
        return max(
            self.lead_follow_up_execution_stale_timeout_seconds,
            self.email_request_timeout_seconds,
        )

    def sales_run_stale_timeout_effective_seconds(self) -> float:
        floor = 2 * self.openai_request_timeout_seconds
        return max(self.sales_run_stale_timeout_seconds, floor)

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def cors_allow_origin_regex(self) -> str | None:
        if self.is_production:
            return None
        # Next.js falls back to 3001 when 3000 is already in use.
        return r"http://(localhost|127\.0\.0\.1)(:\d+)?"

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"

    @model_validator(mode="after")
    def require_secure_secret_outside_dev(self) -> Self:
        if self.environment.lower() in {"development", "test"}:
            return self
        if (
            not self.secret_key
            or self.secret_key == INSECURE_DEFAULT_SECRET
            or len(self.secret_key) < 32
        ):
            raise ValueError("SECRET_KEY must be a unique value of at least 32 characters")
        return self


settings = Settings()

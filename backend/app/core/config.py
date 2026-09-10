from typing import Self

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

INSECURE_DEFAULT_SECRET = "replace-with-a-long-random-local-secret"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=("../.env", ".env"), extra="ignore")

    app_name: str = "FlowPilot"
    environment: str = "development"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    database_url: str = "postgresql+psycopg://app:app@localhost:5432/app"
    redis_url: str = "redis://localhost:6379/0"
    cors_origins: str = "http://localhost:3000"
    secret_key: str = INSECURE_DEFAULT_SECRET
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"
    openai_request_timeout_seconds: float = 60
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

    def agent_execution_stale_timeout_effective_seconds(self) -> float:
        floor = (self.agent_max_tool_iterations + 1) * self.openai_request_timeout_seconds
        return max(self.agent_execution_stale_timeout_seconds, floor)

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

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

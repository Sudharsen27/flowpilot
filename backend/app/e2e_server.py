"""Test-only API process for the local Playwright journey.

Production uvicorn keeps using ``app.main:app`` and ``create_ai_provider()``.
This module is never imported by the API, workers, or webhook path. It starts
only when launched directly, and only after the process proves it is a
disposable E2E environment with no real AI or email credentials.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from urllib.parse import urlparse

from app.ai.provider import AIGenerateRequest, AIGenerateResult
from app.core.config import Settings
from app.core.exceptions import ProviderError

E2E_DATABASE_NAME = "flowpilot_e2e"
E2E_INBOUND_DOMAIN = "inbound.e2e.test"
_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost"})
_POSTGRES_MODES = frozenset({"private", "external"})
_QUALIFICATION_SCHEMA = "lead_qualification"


class E2EIsolationError(RuntimeError):
    """The E2E process is not allowed to start with this configuration."""


class DeterministicE2EProvider:
    """Return one fixed qualification. This object is not registered in the AI factory."""

    def generate(self, request: AIGenerateRequest) -> AIGenerateResult:
        if request.json_schema_name != _QUALIFICATION_SCHEMA:
            raise ProviderError("E2E provider only answers lead qualification")
        payload = {
            "summary": "The customer asked for pricing and a demo.",
            "intent": "REQUEST_DEMO",
            "qualification": "NEEDS_MORE_INFORMATION",
            "qualification_reasons": ["The reply asks for a demo."],
            "confidence": 0.8,
            "extracted_contact": {"name": None, "email": None, "phone": None},
            "extracted_company": {"name": None},
            "buying_signals": ["request pricing", "request demo"],
            "missing_information": ["team size"],
        }
        return AIGenerateResult(
            output_text=json.dumps(payload),
            provider="e2e",
            model="deterministic",
        )


def _present(value: str | None) -> bool:
    return bool(value and value.strip())


def assert_e2e_isolation(current: Settings) -> None:
    if current.environment.lower() != "test" or current.is_production:
        raise E2EIsolationError("E2E server requires ENVIRONMENT=test")
    database = urlparse(current.database_url)
    if database.hostname not in _LOOPBACK_HOSTS:
        raise E2EIsolationError("E2E server only accepts a loopback database")
    database_name = database.path.rstrip("/").rsplit("/", 1)[-1]
    if database_name != E2E_DATABASE_NAME:
        raise E2EIsolationError("E2E server requires the flowpilot_e2e database")
    if (
        _present(current.openai_api_key)
        or _present(current.groq_api_key)
        or _present(current.resend_api_key)
    ):
        raise E2EIsolationError("E2E server refuses OpenAI, Groq, and Resend credentials")
    typesafe_key = current.typesafe_api_key
    if typesafe_key is not None and typesafe_key.get_secret_value().strip():
        raise E2EIsolationError("E2E server refuses a TypeSafe API key")
    webhook_secret = current.resend_webhook_secret
    if webhook_secret is None or not webhook_secret.get_secret_value().strip():
        raise E2EIsolationError("E2E server requires a test inbound webhook secret")
    inbound_domain = (current.resend_inbound_domain or "").strip().lower()
    if inbound_domain != E2E_INBOUND_DOMAIN:
        raise E2EIsolationError("E2E server requires the inbound.e2e.test domain")


def _run(command: list[str], *, cwd: Path | None = None) -> None:
    subprocess.run(command, cwd=cwd, check=True)


def e2e_postgres_mode() -> str:
    """Select private initdb for local runs, or an already provided loopback database.

    ``external`` is for CI, where a disposable Postgres service is already
    listening. It does not relax the database name, host, or credential checks.
    """
    mode = os.environ.get("E2E_POSTGRES_MODE", "private")
    if mode not in _POSTGRES_MODES:
        raise E2EIsolationError("E2E_POSTGRES_MODE must be private or external")
    return mode


def prepare_e2e_database() -> None:
    """Migrate the disposable database before the API listens.

    Local runs start a private cluster on port 5433 because the shared ``app``
    role cannot create a database. CI sets ``E2E_POSTGRES_MODE=external`` and
    supplies that same loopback database from a job-scoped Postgres service.
    """
    if e2e_postgres_mode() == "external":
        backend_dir = Path(__file__).resolve().parents[1]
        _run(["python3", "-m", "alembic", "upgrade", "head"], cwd=backend_dir)
        return

    data_dir = Path(os.environ.get("E2E_POSTGRES_DIR", "")).expanduser()
    if not data_dir.parts or data_dir == Path("."):
        raise E2EIsolationError("E2E_POSTGRES_DIR is required")
    port = os.environ.get("E2E_POSTGRES_PORT", "5433")
    data_dir.mkdir(parents=True, exist_ok=True)
    if not (data_dir / "PG_VERSION").exists():
        _run(
            [
                "initdb",
                "-D",
                str(data_dir),
                "-U",
                "app",
                "--auth-local=trust",
                "--auth-host=trust",
                "--encoding=UTF8",
                "--no-instructions",
            ]
        )
    status = subprocess.run(["pg_ctl", "-D", str(data_dir), "status"], check=False)
    if status.returncode != 0:
        _run(
            [
                "pg_ctl",
                "-D",
                str(data_dir),
                "-l",
                str(data_dir / "server.log"),
                "-o",
                f"-p {port} -h 127.0.0.1",
                "start",
            ]
        )
    created = subprocess.run(
        [
            "psql",
            "-h",
            "127.0.0.1",
            "-p",
            port,
            "-U",
            "app",
            "-d",
            "postgres",
            "-v",
            "ON_ERROR_STOP=1",
            "-c",
            "CREATE DATABASE flowpilot_e2e",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if created.returncode != 0 and "already exists" not in created.stderr:
        raise E2EIsolationError(created.stderr.strip() or "could not create flowpilot_e2e")
    backend_dir = Path(__file__).resolve().parents[1]
    _run(["python3", "-m", "alembic", "upgrade", "head"], cwd=backend_dir)


def main() -> None:
    from app.core.config import settings

    try:
        assert_e2e_isolation(settings)
        prepare_e2e_database()
    except E2EIsolationError as exc:
        raise SystemExit(str(exc)) from exc

    import uvicorn

    from app.api.deps import get_ai_provider
    from app.main import app

    app.dependency_overrides[get_ai_provider] = lambda: DeterministicE2EProvider()
    port = int(os.environ.get("API_PORT", "8010"))
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")


if __name__ == "__main__":
    main()

import inspect

import pytest
from fastapi.testclient import TestClient

import app.main as main_module
from app.api import health as health_module
from app.main import app

client = TestClient(app)


def test_health_returns_ok() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "api"
    assert "database" not in response.text.lower() or "checks" not in body


def test_ready_reports_database(client: TestClient) -> None:
    response = client.get("/health/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "checks": {"database": "ok"}}


def test_ready_hides_database_failures(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(statement: object, *args: object, **kwargs: object) -> None:
        del statement, args, kwargs
        raise RuntimeError("postgresql://app:super-secret-password@db.internal/app")

    monkeypatch.setattr(health_module, "text", lambda statement: statement)
    monkeypatch.setattr("sqlalchemy.orm.Session.execute", fail)
    response = client.get("/health/ready")
    assert response.status_code == 503
    assert response.json() == {
        "status": "unavailable",
        "checks": {"database": "unavailable"},
    }
    assert "super-secret-password" not in response.text
    assert "postgresql" not in response.text
    live = client.get("/health")
    assert live.status_code == 200
    assert live.json()["status"] == "ok"


def test_api_does_not_start_the_worker() -> None:
    source = inspect.getsource(main_module)
    assert "app.worker" not in source
    assert "FollowUpWorker" not in source
    assert "run_forever" not in source


def test_login_preflight_allows_localhost_fallback_port() -> None:
    response = client.options(
        "/api/v1/auth/login",
        headers={
            "Origin": "http://localhost:3001",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3001"

from fastapi.testclient import TestClient

from app.main import app


def test_unhandled_exception_still_sends_the_frontend_cors_header() -> None:
    @app.get("/__test_unhandled")
    def _boom() -> None:
        raise RuntimeError("secret database detail")

    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.get(
                "/__test_unhandled",
                headers={"Origin": "http://localhost:3000"},
            )
    finally:
        app.router.routes = [
            route
            for route in app.router.routes
            if getattr(route, "path", None) != "/__test_unhandled"
        ]

    assert response.status_code == 500
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert response.json() == {"detail": "Internal server error"}
    assert "secret database detail" not in response.text

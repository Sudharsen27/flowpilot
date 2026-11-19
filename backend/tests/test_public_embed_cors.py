from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.organization import Organization
from tests.test_agent_runtime import _headers
from tests.test_leads import _auth
from tests.test_website_capture import PATH, SETTINGS, _payload, _settings_payload


def test_public_enquiry_cors_allows_listed_origin(
    client: TestClient, db: Session
) -> None:
    created = _auth(client)
    token = created["access_token"]
    slug = created["organization"]["slug"]
    org_id = created["organization"]["id"]
    assert (
        client.patch(
            SETTINGS,
            json=_settings_payload(
                website_capture_enabled=True,
                website_embed_allowed_origins=["https://customer.example"],
            ),
            headers=_headers(token),
        ).status_code
        == 200
    )
    organization = db.get(Organization, org_id)
    assert organization is not None
    assert "customer.example" in (organization.website_embed_allowed_origins or "")

    options = client.options(
        PATH.format(slug=slug),
        headers={
            "Origin": "https://customer.example",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert options.status_code == 204
    assert options.headers.get("access-control-allow-origin") == "https://customer.example"

    denied = client.options(
        PATH.format(slug=slug),
        headers={
            "Origin": "https://evil.example",
            "Access-Control-Request-Method": "POST",
        },
    )
    # Falls through to global CORS when not embed-allowlisted.
    assert denied.status_code in {400, 403}
    assert denied.headers.get("access-control-allow-origin") != "https://evil.example"

    # Hosted form on the app origin still works via global CORS_ORIGINS.
    local = client.options(
        PATH.format(slug=slug),
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert local.status_code == 200
    assert local.headers.get("access-control-allow-origin") == "http://localhost:3000"

    response = client.post(
        PATH.format(slug=slug),
        json=_payload(),
        headers={"Origin": "https://customer.example"},
    )
    assert response.status_code == 204
    assert response.headers.get("access-control-allow-origin") == "https://customer.example"

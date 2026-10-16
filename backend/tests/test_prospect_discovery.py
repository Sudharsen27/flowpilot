from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.activity_event import ActivityEvent
from app.models.lead import Lead
from app.models.webhook import WebhookDelivery
from app.models.workflow import WorkflowRun
from tests.test_agent_runtime import _headers
from tests.test_leads import _auth, _create


def _preview(client: TestClient, token: str, contents: bytes, *, content_type: str = "text/csv"):
    return client.post(
        "/api/v1/prospect-discovery/preview",
        content=contents,
        headers={**_headers(token), "Content-Type": content_type},
    )


def test_preview_validates_csv_and_detects_duplicates_without_writes(
    client: TestClient, db: Session
) -> None:
    token = _auth(client)["access_token"]
    existing = _create(client, token, name="Existing", email="saved@example.com").json()
    lead_count = db.scalar(select(func.count()).select_from(Lead))
    activity_count = db.scalar(select(func.count()).select_from(ActivityEvent))
    webhook_count = db.scalar(select(func.count()).select_from(WebhookDelivery))
    workflow_count = db.scalar(select(func.count()).select_from(WorkflowRun))
    csv_data = (
        b"Company Name,Email,Name,Notes\n"
        b'"Acme, Inc",first@example.com,Ada,"Said ""hello"""\n'
        b"Other,saved@example.com,Bea,Existing\n"
        b"Other,first@example.com,Cy,Repeated\n"
        b"Broken,not-an-email,Dee,Invalid\n"
    )

    response = _preview(client, token, csv_data)

    assert response.status_code == 200
    body = response.json()
    assert [column["label"] for column in body["columns"]] == [
        "Company Name",
        "Email",
        "Name",
        "Notes",
    ]
    assert body["rows"][0]["cells"] == [
        "Acme, Inc",
        "first@example.com",
        "Ada",
        'Said "hello"',
    ]
    assert body["summary"] == {
        "total_rows": 4,
        "valid_rows": 3,
        "invalid_rows": 1,
        "duplicate_rows": 2,
    }
    assert "EXISTING_EMAIL" in body["rows"][1]["duplicate_reasons"]
    assert body["rows"][2]["duplicate_of_row"] == 2
    assert "IN_FILE_EMAIL" in body["rows"][2]["duplicate_reasons"]
    assert body["rows"][3]["errors"][0]["code"] == "invalid_email"
    assert db.scalar(select(func.count()).select_from(Lead)) == lead_count
    assert db.scalar(select(func.count()).select_from(ActivityEvent)) == activity_count
    assert db.scalar(select(func.count()).select_from(WebhookDelivery)) == webhook_count
    assert db.scalar(select(func.count()).select_from(WorkflowRun)) == workflow_count
    assert db.get(Lead, existing["id"]).email == "saved@example.com"


def test_preview_accepts_utf8_bom_and_flags_blank_and_extra_columns(client: TestClient) -> None:
    token = _auth(client)["access_token"]
    response = _preview(
        client,
        token,
        "\ufeffName,Email\nAda,ada@example.com\n\nBea,bea@example.com,unexpected\n".encode(),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["rows"][0]["valid"] is True
    assert "blank_row" in {issue["code"] for issue in body["rows"][1]["errors"]}
    assert "extra_columns" in {issue["code"] for issue in body["rows"][2]["errors"]}
    assert body["rows"][0]["row_number"] == 2
    assert body["rows"][1]["row_number"] == 3


def test_preview_reports_missing_and_duplicate_headers(client: TestClient) -> None:
    token = _auth(client)["access_token"]
    response = _preview(client, token, b"Email,email,Company\na@example.com,b@example.com,Acme\n")

    assert response.status_code == 200
    codes = {issue["code"] for issue in response.json()["issues"]}
    assert "duplicate_header" in codes
    assert "missing_required_header" in codes
    assert response.json()["rows"][0]["valid"] is False


def test_preview_detects_name_company_duplicates(client: TestClient) -> None:
    token = _auth(client)["access_token"]
    response = _preview(
        client,
        token,
        b"Name,Email,Company\nAda,ada@example.com,Acme\n ada  ,other@example.com, acme \n",
    )

    assert response.status_code == 200
    row = response.json()["rows"][1]
    assert row["duplicate_of_row"] == 2
    assert "IN_FILE_NAME_COMPANY" in row["duplicate_reasons"]


def test_preview_reports_malformed_csv_and_empty_file(client: TestClient) -> None:
    token = _auth(client)["access_token"]
    malformed = _preview(client, token, b'Name,Email\n"Unclosed,ada@example.com\n')
    empty = _preview(client, token, b"")

    assert malformed.status_code == 200
    assert malformed.json()["rows"][-1]["errors"][0]["code"] == "malformed_csv"
    assert empty.status_code == 200
    assert empty.json()["issues"][0]["code"] == "empty_file"


def test_preview_rejects_unauthenticated_unsupported_and_non_utf8_requests(
    client: TestClient,
) -> None:
    assert client.post(
        "/api/v1/prospect-discovery/preview",
        content=b"Name\nAda\n",
        headers={"Content-Type": "text/csv"},
    ).status_code == 401
    token = _auth(client)["access_token"]
    assert _preview(client, token, b"Name\nAda\n", content_type="text/plain").status_code == 415
    assert _preview(client, token, b"\xff", content_type="text/csv").status_code == 422


def test_preview_limits_file_size_and_record_count(client: TestClient, monkeypatch: Any) -> None:
    from app.api.v1 import prospect_discovery
    from app.services import prospect_csv_preview_service

    token = _auth(client)["access_token"]
    monkeypatch.setattr(prospect_discovery, "MAX_PROSPECT_CSV_BYTES", 8)
    assert _preview(client, token, b"Name\n" + b"a" * 8).status_code == 413

    monkeypatch.setattr(prospect_discovery, "MAX_PROSPECT_CSV_BYTES", 2 * 1024 * 1024)
    monkeypatch.setattr(prospect_csv_preview_service, "MAX_PROSPECT_CSV_COLUMNS", 2)
    assert _preview(client, token, b"Name,Email,Phone\nAda,a@example.com,555\n").status_code == 413

    monkeypatch.setattr(prospect_csv_preview_service, "MAX_PROSPECT_CSV_COLUMNS", 100)
    monkeypatch.setattr(prospect_csv_preview_service, "MAX_PROSPECT_CSV_ROWS", 1)
    assert _preview(client, token, b"Name\nAda\nBea\n").status_code == 413

    monkeypatch.setattr(prospect_csv_preview_service, "MAX_PROSPECT_CSV_ROWS", 500)
    monkeypatch.setattr(prospect_discovery, "MAX_PROSPECT_PREVIEW_RESPONSE_BYTES", 1)
    assert _preview(client, token, b"Name\nAda\n").status_code == 413


def test_existing_email_matches_are_organization_scoped(client: TestClient) -> None:
    first = _auth(client, email="first@example.com", organization_name="First")
    second = _auth(client, email="second@example.com", organization_name="Second")
    _create(client, first["access_token"], name="Private", email="shared@example.com")

    response = _preview(client, second["access_token"], b"Name,Email\nAda,shared@example.com\n")

    assert response.status_code == 200
    assert response.json()["rows"][0]["duplicate_reasons"] == []
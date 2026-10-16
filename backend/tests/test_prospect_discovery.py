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


def _import(
    client: TestClient,
    token: str,
    contents: bytes,
    *,
    confirmed: bool = True,
    content_type: str = "text/csv",
):
    headers = {**_headers(token), "Content-Type": content_type}
    if confirmed:
        headers["X-Prospect-Import-Confirmed"] = "true"
    return client.post("/api/v1/prospect-discovery/import", content=contents, headers=headers)


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


def test_import_requires_authentication_and_explicit_confirmation(
    client: TestClient, db: Session
) -> None:
    csv_data = b"Name,Email\nAda,ada@example.com\n"
    assert client.post(
        "/api/v1/prospect-discovery/import",
        content=csv_data,
        headers={"Content-Type": "text/csv", "X-Prospect-Import-Confirmed": "true"},
    ).status_code == 401

    token = _auth(client)["access_token"]
    response = _import(client, token, csv_data, confirmed=False)

    assert response.status_code == 428
    assert response.json()["detail"] == "Explicit confirmation is required before importing prospects."
    assert db.scalar(select(func.count()).select_from(Lead)) == 0


def test_import_creates_normalized_import_leads_and_ignores_unsupported_fields(
    client: TestClient, db: Session
) -> None:
    auth = _auth(client)
    csv_data = (
        b"Name,Email,Phone,Company,Notes,Enquiry,Source,Status,Territory\n"
        b" Ada Lovelace ,ADA@EXAMPLE.COM, 555-0100 , Acme , note , enquiry ,WEBSITE,CONVERTED,West\n"
    )

    response = _import(client, auth["access_token"], csv_data)

    assert response.status_code == 200
    assert response.json()["total_rows"] == 1
    assert response.json()["imported_count"] == 1
    assert response.json()["skipped_count"] == 0
    assert response.json()["failed_count"] == 0
    lead = db.scalar(select(Lead).where(Lead.organization_id == auth["organization"]["id"]))
    assert lead is not None
    assert lead.name == "Ada Lovelace"
    assert lead.email == "ADA@example.com"
    assert lead.phone == "555-0100"
    assert lead.company == "Acme"
    assert lead.notes == "note"
    assert lead.enquiry == "enquiry"
    assert lead.source == "IMPORT"
    assert lead.status == "NEW"


def test_import_skips_invalid_and_duplicate_rows_and_retries_are_safe_by_email(
    client: TestClient, db: Session
) -> None:
    token = _auth(client)["access_token"]
    _create(client, token, name="Existing", email="saved@example.com")
    csv_data = (
        b"Name,Email,Company\n"
        b"Ada,ada@example.com,Acme\n"
        b"Ada Two,ADA@EXAMPLE.COM,Other\n"
        b"Saved,saved@example.com,Other\n"
        b"Invalid,not-an-email,Other\n"
        b" ada ,other@example.com, acme \n"
    )

    response = _import(client, token, csv_data)
    repeated = _import(client, token, b"Name,Email\nAda,ada@example.com\n")

    assert response.status_code == 200
    body = response.json()
    assert body["imported_count"] == 1
    assert body["skipped_count"] == 4
    assert [row["reason_code"] for row in body["rows"]] == [
        None,
        "IN_FILE_EMAIL",
        "EXISTING_EMAIL",
        "INVALID_ROW",
        "IN_FILE_NAME_COMPANY",
    ]
    assert body["rows"][1]["duplicate_of_row"] == 2
    assert repeated.status_code == 200
    assert repeated.json()["imported_count"] == 0
    assert repeated.json()["rows"][0]["reason_code"] == "EXISTING_EMAIL"
    assert db.scalar(select(func.count()).select_from(Lead)) == 2


def test_import_is_scoped_to_authenticated_organization(client: TestClient, db: Session) -> None:
    first = _auth(client, email="first@example.com", organization_name="First")
    second = _auth(client, email="second@example.com", organization_name="Second")
    _create(client, first["access_token"], name="Private", email="shared@example.com")

    response = _import(
        client,
        second["access_token"],
        b"Name,Email\nShared,shared@example.com\n",
    )

    assert response.status_code == 200
    assert response.json()["imported_count"] == 1
    assert response.json()["skipped_count"] == 0
    leads = list(db.scalars(select(Lead).order_by(Lead.created_at)))
    second_lead = next(lead for lead in leads if lead.organization_id == second["organization"]["id"])
    assert second_lead.name == "Shared"
    assert second_lead.email == "shared@example.com"
    assert second_lead.organization_id != first["organization"]["id"]


def test_import_rejects_malformed_headers_encoding_and_unsupported_content_type(
    client: TestClient,
) -> None:
    token = _auth(client)["access_token"]

    assert _import(client, token, b"\xff").status_code == 422
    assert _import(client, token, b"Email,email\na@example.com,b@example.com\n").status_code == 422
    assert _import(client, token, b"Name\nAda\n", content_type="text/plain").status_code == 415


def test_import_enforces_file_row_and_column_limits(client: TestClient, monkeypatch: Any) -> None:
    from app.api.v1 import prospect_discovery
    from app.services import prospect_csv_preview_service

    token = _auth(client)["access_token"]
    monkeypatch.setattr(prospect_discovery, "MAX_PROSPECT_CSV_BYTES", 8)
    assert _import(client, token, b"Name\n" + b"a" * 8).status_code == 413

    monkeypatch.setattr(prospect_discovery, "MAX_PROSPECT_CSV_BYTES", 2 * 1024 * 1024)
    monkeypatch.setattr(prospect_csv_preview_service, "MAX_PROSPECT_CSV_COLUMNS", 1)
    assert _import(client, token, b"Name,Email\nAda,a@example.com\n").status_code == 413

    monkeypatch.setattr(prospect_csv_preview_service, "MAX_PROSPECT_CSV_COLUMNS", 100)
    monkeypatch.setattr(prospect_csv_preview_service, "MAX_PROSPECT_CSV_ROWS", 1)
    assert _import(client, token, b"Name\nAda\nBea\n").status_code == 413


def test_import_side_effects_are_per_created_lead_and_failed_rows_roll_back(
    client: TestClient,
    db: Session,
    monkeypatch: Any,
) -> None:
    from app.models.activity_event import ActivityActorType
    from app.models.lead_email_send import LeadEmailSend
    from app.models.lead_qualification import LeadQualification
    from app.models.lead_response_draft import LeadResponseDraft
    from app.models.sales_run import SalesRun
    from app.models.webhook import WebhookDelivery, WebhookEndpoint, WebhookEventType
    from app.models.workflow import WorkflowAction, WorkflowRule, WorkflowTrigger
    from app.services import webhook_events

    auth = _auth(client)
    organization_id = auth["organization"]["id"]
    endpoint = WebhookEndpoint(
        organization_id=organization_id,
        name="Lead import test",
        url="https://example.com/webhook",
        events=[str(WebhookEventType.LEAD_CREATED)],
        secret_salt="test-salt",
        secret_hint="test",
    )
    rule = WorkflowRule(
        organization_id=organization_id,
        name="Lead import test",
        trigger=WorkflowTrigger.LEAD_CREATED,
        action=WorkflowAction.ANALYZE_LEAD,
        source_filter="IMPORT",
        enabled=True,
        revision=1,
    )
    db.add_all([endpoint, rule])
    db.commit()

    original_lead_created = webhook_events.lead_created

    def fail_one_row(session: Session, lead: Lead) -> None:
        if lead.name == "Rollback":
            raise RuntimeError("injected enqueue failure")
        original_lead_created(session, lead)

    monkeypatch.setattr(webhook_events, "lead_created", fail_one_row)
    response = _import(
        client,
        auth["access_token"],
        b"Name,Email\n"
        b"Rollback,rollback@example.com\n"
        b"Created,created@example.com\n"
        b"Created again,created@example.com\n"
        b"Invalid,not-an-email\n",
    )

    assert response.status_code == 200
    assert response.json()["imported_count"] == 1
    assert response.json()["failed_count"] == 1
    assert response.json()["skipped_count"] == 2
    created = db.scalar(select(Lead).where(Lead.email == "created@example.com"))
    assert created is not None
    assert db.scalar(select(Lead).where(Lead.email == "rollback@example.com")) is None
    activity = db.scalar(
        select(ActivityEvent).where(ActivityEvent.lead_id == created.id)
    )
    assert activity is not None
    assert activity.actor_type == ActivityActorType.USER
    assert activity.actor_user_id == auth["user"]["id"]
    assert db.scalar(select(func.count()).select_from(ActivityEvent)) == 1
    assert db.scalar(select(func.count()).select_from(WorkflowRun)) == 1
    assert db.scalar(select(func.count()).select_from(WebhookDelivery)) == 1
    delivery = db.scalar(select(WebhookDelivery))
    assert delivery is not None
    assert delivery.event_type == WebhookEventType.LEAD_CREATED
    assert db.scalar(select(func.count()).select_from(LeadQualification)) == 0
    assert db.scalar(select(func.count()).select_from(LeadResponseDraft)) == 0
    assert db.scalar(select(func.count()).select_from(LeadEmailSend)) == 0
    assert db.scalar(select(func.count()).select_from(SalesRun)) == 0
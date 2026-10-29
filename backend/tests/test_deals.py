from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.activity_event import ActivityEvent
from app.models.deal import (
    DEAL_STAGE_DEFAULT_PROBABILITY,
    Deal,
    DealStage,
    DealStageEvent,
    effective_probability,
)
from app.models.lead import Lead
from app.models.membership import MembershipRole
from app.models.organization import Organization
from app.services.activity_service import ActivityService
from tests.conftest import TestingSessionLocal
from tests.test_agent_api import _add_org_member
from tests.test_agent_runtime import _headers
from tests.test_leads import _auth
from tests.test_leads import _create as _create_lead


def _deal(client: TestClient, token: str, **overrides: Any) -> Any:
    body: dict[str, Any] = {
        "name": "Acme expansion",
        "amount": "125000.50",
        "expected_close_date": "2026-12-15",
    }
    body.update(overrides)
    return client.post("/api/v1/deals", json=body, headers=_headers(token))


def _user_id(client: TestClient, token: str) -> str:
    return str(client.get("/api/v1/users/me", headers=_headers(token)).json()["user"]["id"])


def _org_with_roles(client: TestClient, db: Session) -> dict[str, Any]:
    owner = _auth(client, email="owner@example.com", organization_name="Org A")
    org_id = owner["organization"]["id"]
    admin = _add_org_member(db, org_id, email="admin@example.com", role=MembershipRole.ADMIN)
    member = _add_org_member(db, org_id, email="member@example.com", role=MembershipRole.MEMBER)
    return {
        "org_id": org_id,
        "owner": owner["access_token"],
        "owner_id": owner["user"]["id"],
        "admin": admin,
        "admin_id": _user_id(client, admin),
        "member": member,
        "member_id": _user_id(client, member),
    }


def _stage(client: TestClient, token: str, deal: dict[str, Any], **body: Any) -> Any:
    return client.post(
        f"/api/v1/deals/{deal['id']}/stage",
        json={"expected_revision": deal["revision"], **body},
        headers=_headers(token),
    )


def _history(client: TestClient, token: str, deal_id: str) -> list[dict[str, Any]]:
    response = client.get(f"/api/v1/deals/{deal_id}/history", headers=_headers(token))
    assert response.status_code == 200
    return list(response.json()["items"])


def test_unauthenticated_deal_requests_are_rejected(client: TestClient) -> None:
    assert client.get("/api/v1/deals").status_code == 401
    assert client.post("/api/v1/deals", json={}).status_code == 401
    assert client.get("/api/v1/deals/deal-1").status_code == 401
    assert client.patch("/api/v1/deals/deal-1", json={}).status_code == 401
    assert client.post("/api/v1/deals/deal-1/stage", json={}).status_code == 401
    assert client.get("/api/v1/deals/deal-1/history").status_code == 401


def test_create_get_list_and_defaults(client: TestClient) -> None:
    auth = _auth(client)
    token = auth["access_token"]
    created = _deal(client, token, description="  Upsell to the platform plan  ")
    assert created.status_code == 201
    deal = created.json()
    assert deal["name"] == "Acme expansion"
    assert deal["description"] == "Upsell to the platform plan"
    assert deal["amount"] == "125000.50"
    assert deal["currency"] == "INR"
    assert deal["stage"] == "QUALIFICATION"
    assert deal["probability"] is None
    assert deal["effective_probability"] == 10
    assert deal["probability_source"] == "STAGE_DEFAULT"
    assert deal["owner_user_id"] == auth["user"]["id"]
    assert deal["owner_name"] == auth["user"]["name"]
    assert deal["closed_at"] is None
    assert deal["revision"] == 1
    assert deal["expected_close_date"] == "2026-12-15"

    fetched = client.get(f"/api/v1/deals/{deal['id']}", headers=_headers(token))
    assert fetched.status_code == 200
    assert fetched.json() == deal

    listed = client.get("/api/v1/deals", headers=_headers(token)).json()
    assert listed["total"] == 1
    assert listed["limit"] == 20
    assert listed["offset"] == 0
    assert listed["items"][0]["id"] == deal["id"]
    assert client.get("/api/v1/deals/missing", headers=_headers(token)).status_code == 404


def test_list_filters_search_and_pagination(client: TestClient, db: Session) -> None:
    roles = _org_with_roles(client, db)
    token = roles["owner"]
    _deal(client, token, name="Alpha renewal", expected_close_date="2026-11-10")
    proposal = _deal(client, token, name="Beta rollout", expected_close_date="2026-12-20").json()
    _stage(client, token, proposal, stage="PROPOSAL")
    _deal(
        client,
        roles["admin"],
        name="Gamma pilot",
        description="Retail 100% rollout",
        expected_close_date="2027-01-05",
    )

    def ids(**params: Any) -> list[str]:
        response = client.get("/api/v1/deals", params=params, headers=_headers(token))
        assert response.status_code == 200
        return [item["name"] for item in response.json()["items"]]

    assert ids(stage="PROPOSAL") == ["Beta rollout"]
    assert ids(owner_user_id=roles["admin_id"]) == ["Gamma pilot"]
    assert sorted(ids(close_date_from="2026-12-01", close_date_to="2026-12-31")) == [
        "Beta rollout"
    ]
    assert ids(q="ALPHA") == ["Alpha renewal"]
    assert ids(q="100%") == ["Gamma pilot"]
    # "%" is matched literally, not as a wildcard that would return every deal.
    assert ids(q="%") == ["Gamma pilot"]
    assert ids(q="_") == []
    page = client.get("/api/v1/deals?limit=2&offset=2", headers=_headers(token)).json()
    assert page["total"] == 3 and len(page["items"]) == 1
    bad_range = client.get(
        "/api/v1/deals?close_date_from=2027-01-01&close_date_to=2026-01-01",
        headers=_headers(token),
    )
    assert bad_range.status_code == 422
    assert client.get("/api/v1/deals?stage=WON", headers=_headers(token)).status_code == 422
    assert client.get("/api/v1/deals?limit=101", headers=_headers(token)).status_code == 422


@pytest.mark.parametrize("stage", [stage.value for stage in DealStage])
def test_every_stage_can_be_created_with_its_default_probability(
    client: TestClient, stage: str
) -> None:
    token = _auth(client)["access_token"]
    extra = {"lost_reason": "Chose a competitor"} if stage == "CLOSED_LOST" else {}
    created = _deal(client, token, stage=stage, **extra)
    assert created.status_code == 201, created.json()
    deal = created.json()
    assert deal["stage"] == stage
    assert deal["effective_probability"] == DEAL_STAGE_DEFAULT_PROBABILITY[DealStage(stage)]
    assert (deal["closed_at"] is not None) == (stage in {"CLOSED_WON", "CLOSED_LOST"})


def test_stage_defaults_are_centralized() -> None:
    assert [DEAL_STAGE_DEFAULT_PROBABILITY[stage] for stage in DealStage] == [
        10,
        25,
        50,
        75,
        100,
        0,
    ]
    assert effective_probability("PROPOSAL", None) == 50
    assert effective_probability("PROPOSAL", 65) == 65
    assert effective_probability("CLOSED_WON", 65) == 100


def test_probability_override_and_validation(client: TestClient) -> None:
    token = _auth(client)["access_token"]
    deal = _deal(client, token, probability=35).json()
    assert deal["probability"] == 35
    assert deal["effective_probability"] == 35
    assert deal["probability_source"] == "OVERRIDE"

    cleared = client.patch(
        f"/api/v1/deals/{deal['id']}",
        json={"expected_revision": 1, "probability": None},
        headers=_headers(token),
    ).json()
    assert cleared["probability"] is None
    assert cleared["effective_probability"] == 10
    assert cleared["probability_source"] == "STAGE_DEFAULT"

    for value in (-1, 101, "high"):
        assert _deal(client, token, probability=value).status_code == 422
    closed = _deal(client, token, stage="CLOSED_WON", probability=80)
    assert closed.status_code == 422

    moved = _stage(client, token, cleared, stage="DISCOVERY", probability=40).json()
    assert moved["effective_probability"] == 40
    won = _stage(client, token, moved, stage="CLOSED_WON").json()
    assert won["probability"] is None
    assert won["effective_probability"] == 100
    patched = client.patch(
        f"/api/v1/deals/{won['id']}",
        json={"expected_revision": won["revision"], "probability": 50},
        headers=_headers(token),
    )
    assert patched.status_code == 422


def test_money_is_exact_and_serialized_as_two_decimal_strings(
    client: TestClient, db: Session
) -> None:
    token = _auth(client)["access_token"]
    cases = {
        "0.10": "0.10",
        "1": "1.00",
        "999999999999.99": "999999999999.99",
        "  42.5 ": "42.50",
        7: "7.00",
    }
    for raw, expected in cases.items():
        response = _deal(client, token, amount=raw)
        assert response.status_code == 201, (raw, response.json())
        assert response.json()["amount"] == expected
        stored = db.get(Deal, response.json()["id"])
        assert stored is not None
        assert Decimal(stored.amount) == Decimal(expected)


@pytest.mark.parametrize(
    "amount",
    ["-0.01", "1.001", "1000000000000.00", "abc", "NaN", "Infinity", 12.5, True, None, ""],
)
def test_invalid_amounts_are_rejected(client: TestClient, amount: object) -> None:
    token = _auth(client)["access_token"]
    assert _deal(client, token, amount=amount).status_code == 422


def test_invalid_stage_currency_dates_and_fields_are_rejected(client: TestClient) -> None:
    token = _auth(client)["access_token"]
    assert _deal(client, token, stage="WON").status_code == 422
    assert _deal(client, token, currency="USD").status_code == 422
    assert _deal(client, token, currency="RUPEES").status_code == 422
    assert _deal(client, token, currency="inr").status_code == 201
    assert _deal(client, token, expected_close_date="2026-02-30").status_code == 422
    assert _deal(client, token, expected_close_date="soon").status_code == 422
    assert _deal(client, token, expected_close_date=None).status_code == 422
    assert _deal(client, token, name="   ").status_code == 422
    assert _deal(client, token, unknown_field=1).status_code == 422
    assert _deal(client, token, stage="CLOSED_LOST").status_code == 422
    assert _deal(client, token, lost_reason="No budget").status_code == 422

    deal = _deal(client, token).json()
    for body in (
        {"stage": "PROPOSAL"},
        {"currency": "USD"},
        {"lead_id": "lead-1"},
        {"name": None},
        {"amount": None},
        {"expected_close_date": None},
    ):
        patched = client.patch(
            f"/api/v1/deals/{deal['id']}",
            json={"expected_revision": 1, **body},
            headers=_headers(token),
        )
        assert patched.status_code == 422, body
    missing_revision = client.patch(
        f"/api/v1/deals/{deal['id']}", json={"name": "New"}, headers=_headers(token)
    )
    assert missing_revision.status_code == 422


def test_deals_are_isolated_between_organizations(client: TestClient) -> None:
    org_a = _auth(client, email="a@example.com", organization_name="Org A")
    org_b = _auth(client, email="b@example.com", organization_name="Org B")
    deal = _deal(client, org_a["access_token"]).json()
    token_b = org_b["access_token"]
    assert client.get("/api/v1/deals", headers=_headers(token_b)).json()["total"] == 0
    assert client.get(f"/api/v1/deals/{deal['id']}", headers=_headers(token_b)).status_code == 404
    patched = client.patch(
        f"/api/v1/deals/{deal['id']}",
        json={"expected_revision": 1, "name": "Hijacked"},
        headers=_headers(token_b),
    )
    assert patched.status_code == 404
    assert _stage(client, token_b, deal, stage="PROPOSAL").status_code == 404
    history = client.get(f"/api/v1/deals/{deal['id']}/history", headers=_headers(token_b))
    assert history.status_code == 404
    unchanged = client.get(
        f"/api/v1/deals/{deal['id']}", headers=_headers(org_a["access_token"])
    ).json()
    assert unchanged["name"] == "Acme expansion"
    assert unchanged["revision"] == 1


def test_cross_organization_lead_and_owner_are_rejected(client: TestClient) -> None:
    org_a = _auth(client, email="a@example.com", organization_name="Org A")
    org_b = _auth(client, email="b@example.com", organization_name="Org B")
    lead_b = _create_lead(client, org_b["access_token"]).json()
    with_foreign_lead = _deal(client, org_a["access_token"], lead_id=lead_b["id"])
    assert with_foreign_lead.status_code == 404
    assert with_foreign_lead.json()["detail"] == "Lead not found"
    lead_after = client.get(
        f"/api/v1/leads/{lead_b['id']}", headers=_headers(org_b["access_token"])
    ).json()
    assert lead_after["status"] == "NEW"

    with_foreign_owner = _deal(
        client, org_a["access_token"], owner_user_id=org_b["user"]["id"]
    )
    assert with_foreign_owner.status_code == 422
    assert _deal(client, org_a["access_token"], owner_user_id="no-such-user").status_code == 422
    assert client.get("/api/v1/deals", headers=_headers(org_a["access_token"])).json()["total"] == 0


@pytest.mark.parametrize("role", ["owner", "admin", "member"])
def test_every_role_can_view_create_edit_and_move_deals(
    client: TestClient, db: Session, role: str
) -> None:
    roles = _org_with_roles(client, db)
    token = roles[role]
    created = _deal(client, token)
    assert created.status_code == 201
    deal = created.json()
    assert deal["owner_user_id"] == roles[f"{role}_id"]
    edited = client.patch(
        f"/api/v1/deals/{deal['id']}",
        json={"expected_revision": 1, "name": "Renamed", "amount": "10.00"},
        headers=_headers(token),
    )
    assert edited.status_code == 200
    moved = _stage(client, token, edited.json(), stage="PROPOSAL")
    assert moved.status_code == 200
    assert client.get("/api/v1/deals", headers=_headers(token)).json()["total"] == 1
    assert len(_history(client, token, deal["id"])) == 3


def test_only_owner_and_admin_can_reassign_deal_owners(
    client: TestClient, db: Session
) -> None:
    roles = _org_with_roles(client, db)
    member_deal = _deal(client, roles["member"]).json()

    denied = client.patch(
        f"/api/v1/deals/{member_deal['id']}",
        json={"expected_revision": 1, "owner_user_id": roles["admin_id"]},
        headers=_headers(roles["member"]),
    )
    assert denied.status_code == 403
    assert _deal(client, roles["member"], owner_user_id=roles["admin_id"]).status_code == 403
    unassign = client.patch(
        f"/api/v1/deals/{member_deal['id']}",
        json={"expected_revision": 1, "owner_user_id": None},
        headers=_headers(roles["member"]),
    )
    assert unassign.status_code == 403
    same_owner = client.patch(
        f"/api/v1/deals/{member_deal['id']}",
        json={"expected_revision": 1, "owner_user_id": roles["member_id"], "name": "Kept"},
        headers=_headers(roles["member"]),
    )
    assert same_owner.status_code == 200

    for manager in ("owner", "admin"):
        current = client.get(
            f"/api/v1/deals/{member_deal['id']}", headers=_headers(roles[manager])
        ).json()
        target = roles["admin_id"] if manager == "owner" else roles["owner_id"]
        reassigned = client.patch(
            f"/api/v1/deals/{member_deal['id']}",
            json={"expected_revision": current["revision"], "owner_user_id": target},
            headers=_headers(roles[manager]),
        )
        assert reassigned.status_code == 200
        assert reassigned.json()["owner_user_id"] == target
    assigned = _deal(client, roles["admin"], owner_user_id=roles["member_id"])
    assert assigned.status_code == 201
    assert assigned.json()["owner_user_id"] == roles["member_id"]
    unassigned = _deal(client, roles["member"], owner_user_id=None)
    assert unassigned.status_code == 201
    assert unassigned.json()["owner_user_id"] is None


def test_stale_revisions_return_409_and_change_nothing(client: TestClient) -> None:
    token = _auth(client)["access_token"]
    deal = _deal(client, token).json()
    first = client.patch(
        f"/api/v1/deals/{deal['id']}",
        json={"expected_revision": 1, "amount": "200.00"},
        headers=_headers(token),
    )
    assert first.status_code == 200
    assert first.json()["revision"] == 2
    stale_patch = client.patch(
        f"/api/v1/deals/{deal['id']}",
        json={"expected_revision": 1, "amount": "300.00"},
        headers=_headers(token),
    )
    assert stale_patch.status_code == 409
    assert stale_patch.json() == {
        "detail": "This deal changed. Refresh and review the latest version.",
        "current_revision": 2,
    }
    stale_stage = _stage(client, token, deal, stage="PROPOSAL")
    assert stale_stage.status_code == 409
    current = client.get(f"/api/v1/deals/{deal['id']}", headers=_headers(token)).json()
    assert current["amount"] == "200.00"
    assert current["stage"] == "QUALIFICATION"
    assert len(_history(client, token, deal["id"])) == 2


def test_unchanged_updates_do_not_bump_revision_or_write_history(client: TestClient) -> None:
    token = _auth(client)["access_token"]
    deal = _deal(client, token).json()
    same = client.patch(
        f"/api/v1/deals/{deal['id']}",
        json={
            "expected_revision": 1,
            "name": "Acme expansion",
            "amount": "125000.5",
            "expected_close_date": "2026-12-15",
        },
        headers=_headers(token),
    ).json()
    assert same["revision"] == 1
    same_stage = _stage(client, token, deal, stage="QUALIFICATION").json()
    assert same_stage["revision"] == 1
    assert len(_history(client, token, deal["id"])) == 1
    name_only = client.patch(
        f"/api/v1/deals/{deal['id']}",
        json={"expected_revision": 1, "name": "Renamed"},
        headers=_headers(token),
    ).json()
    assert name_only["revision"] == 2
    # Renaming is not an amount, close-date or stage change, so no history row.
    assert len(_history(client, token, deal["id"])) == 1


def test_history_records_creation_stage_amount_and_date_changes(client: TestClient) -> None:
    auth = _auth(client)
    token = auth["access_token"]
    deal = _deal(client, token).json()
    deal = client.patch(
        f"/api/v1/deals/{deal['id']}",
        json={"expected_revision": 1, "amount": "150000.00", "change_reason": "Scope grew"},
        headers=_headers(token),
    ).json()
    deal = client.patch(
        f"/api/v1/deals/{deal['id']}",
        json={"expected_revision": 2, "expected_close_date": "2027-01-31"},
        headers=_headers(token),
    ).json()
    deal = _stage(client, token, deal, stage="PROPOSAL", change_reason="Sent proposal").json()
    deal = _stage(client, token, deal, stage="CLOSED_LOST", lost_reason="Budget cut").json()
    assert deal["lost_reason"] == "Budget cut"
    assert deal["closed_at"] is not None
    reopened = _stage(client, token, deal, stage="NEGOTIATION").json()
    assert reopened["closed_at"] is None
    assert reopened["lost_reason"] is None

    events = _history(client, token, deal["id"])
    assert [event["changes"] for event in events] == [
        ["CREATED"],
        ["AMOUNT"],
        ["EXPECTED_CLOSE_DATE"],
        ["STAGE"],
        ["STAGE"],
        ["STAGE"],
    ]
    created, amount, close_date, proposal, lost, reopen = events
    assert created["previous_stage"] is None
    assert created["new_stage"] == "QUALIFICATION"
    assert created["previous_amount"] is None
    assert created["new_amount"] == "125000.50"
    assert amount["previous_amount"] == "125000.50"
    assert amount["new_amount"] == "150000.00"
    assert amount["change_reason"] == "Scope grew"
    assert close_date["previous_expected_close_date"] == "2026-12-15"
    assert close_date["new_expected_close_date"] == "2027-01-31"
    assert proposal["previous_stage"] == "QUALIFICATION"
    assert proposal["new_stage"] == "PROPOSAL"
    assert proposal["change_reason"] == "Sent proposal"
    assert lost["new_stage"] == "CLOSED_LOST"
    assert reopen["previous_stage"] == "CLOSED_LOST"
    assert all(event["changed_by_user_id"] == auth["user"]["id"] for event in events)
    assert all(event["changed_by_name"] == auth["user"]["name"] for event in events)

    # Re-entering a stage is recorded again: no deduplication.
    again = _stage(client, token, reopened, stage="PROPOSAL").json()
    _stage(client, token, again, stage="NEGOTIATION")
    stages = [event["new_stage"] for event in _history(client, token, deal["id"])]
    assert stages.count("NEGOTIATION") == 2


def test_stage_change_validation(client: TestClient) -> None:
    token = _auth(client)["access_token"]
    deal = _deal(client, token).json()
    assert _stage(client, token, deal, stage="CLOSED_LOST").status_code == 422
    assert (
        _stage(client, token, deal, stage="PROPOSAL", lost_reason="n/a").status_code == 422
    )
    assert _stage(client, token, deal, stage="CLOSED_WON", probability=90).status_code == 422
    assert _stage(client, token, deal, stage="DONE").status_code == 422
    assert (
        _stage(client, token, deal, stage="QUALIFICATION", probability=20).status_code == 422
    )
    lost = _stage(client, token, deal, stage="CLOSED_LOST", lost_reason="Went quiet").json()
    no_reason = client.patch(
        f"/api/v1/deals/{deal['id']}",
        json={"expected_revision": lost["revision"], "lost_reason": None},
        headers=_headers(token),
    )
    assert no_reason.status_code == 422
    new_reason = client.patch(
        f"/api/v1/deals/{deal['id']}",
        json={"expected_revision": lost["revision"], "lost_reason": "Chose a competitor"},
        headers=_headers(token),
    )
    assert new_reason.status_code == 200
    assert new_reason.json()["lost_reason"] == "Chose a competitor"


def test_history_cannot_be_changed_and_deals_cannot_be_deleted(client: TestClient) -> None:
    token = _auth(client)["access_token"]
    deal = _deal(client, token).json()
    history_path = f"/api/v1/deals/{deal['id']}/history"
    for method in ("POST", "PUT", "PATCH", "DELETE"):
        response = client.request(method, history_path, json={}, headers=_headers(token))
        assert response.status_code == 405, method
    deleted = client.delete(f"/api/v1/deals/{deal['id']}", headers=_headers(token))
    assert deleted.status_code == 405
    assert len(_history(client, token, deal["id"])) == 1
    assert client.get(f"/api/v1/deals/{deal['id']}", headers=_headers(token)).status_code == 200


def test_history_pagination_and_missing_deal(client: TestClient) -> None:
    token = _auth(client)["access_token"]
    deal = _deal(client, token).json()
    for stage in ("DISCOVERY", "PROPOSAL", "NEGOTIATION"):
        deal = _stage(client, token, deal, stage=stage).json()
    page = client.get(
        f"/api/v1/deals/{deal['id']}/history?limit=2&offset=1", headers=_headers(token)
    ).json()
    assert page["total"] == 4
    assert [event["new_stage"] for event in page["items"]] == ["DISCOVERY", "PROPOSAL"]
    assert client.get("/api/v1/deals/missing/history", headers=_headers(token)).status_code == 404


def test_creating_a_deal_converts_its_lead_with_activity(client: TestClient, db: Session) -> None:
    auth = _auth(client)
    token = auth["access_token"]
    lead = _create_lead(client, token, name="Ada Prospect").json()
    created = _deal(client, token, lead_id=lead["id"])
    assert created.status_code == 201
    assert created.json()["lead_id"] == lead["id"]
    assert created.json()["lead_name"] == "Ada Prospect"
    lead_after = client.get(f"/api/v1/leads/{lead['id']}", headers=_headers(token)).json()
    assert lead_after["status"] == "CONVERTED"
    events = list(
        db.scalars(
            select(ActivityEvent).where(
                ActivityEvent.lead_id == lead["id"],
                ActivityEvent.title == "Lead status changed",
            )
        )
    )
    assert len(events) == 1
    assert events[0].status == "CONVERTED"
    assert events[0].actor_user_id == auth["user"]["id"]
    assert events[0].dedupe_key == f"lead:{lead['id']}:STATUS:CONVERTED"

    # A second deal for an already converted lead keeps the status and adds no event.
    assert _deal(client, token, lead_id=lead["id"]).status_code == 201
    count = len(
        list(
            db.scalars(
                select(ActivityEvent).where(
                    ActivityEvent.lead_id == lead["id"],
                    ActivityEvent.title == "Lead status changed",
                )
            )
        )
    )
    assert count == 1
    assert _deal(client, token, lead_id="no-such-lead").status_code == 404


def test_failed_lead_conversion_rolls_back_everything(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    token = _auth(client)["access_token"]
    lead = _create_lead(client, token).json()

    def fail(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("activity store unavailable")

    monkeypatch.setattr(ActivityService, "record", fail)
    failed = _deal(client, token, lead_id=lead["id"])
    monkeypatch.undo()
    assert failed.status_code == 500
    assert failed.json() == {"detail": "Internal server error"}

    db.expire_all()
    stored_lead = db.get(Lead, lead["id"])
    assert stored_lead is not None
    assert stored_lead.status == "NEW"
    assert db.scalar(select(Deal)) is None
    assert db.scalar(select(DealStageEvent)) is None
    assert client.get("/api/v1/deals", headers=_headers(token)).json()["total"] == 0


def test_deal_and_history_persist_across_sessions(client: TestClient) -> None:
    token = _auth(client)["access_token"]
    deal = _deal(client, token, amount="98765.43").json()
    _stage(client, token, deal, stage="PROPOSAL")

    fresh = TestingSessionLocal()
    try:
        stored = fresh.get(Deal, deal["id"])
        assert stored is not None
        assert stored.stage == "PROPOSAL"
        assert Decimal(stored.amount) == Decimal("98765.43")
        assert stored.currency == "INR"
        assert stored.revision == 2
        events = list(
            fresh.scalars(select(DealStageEvent).where(DealStageEvent.deal_id == deal["id"]))
        )
        assert sorted(event.new_stage for event in events) == ["PROPOSAL", "QUALIFICATION"]
    finally:
        fresh.close()


def test_organizations_default_to_inr(client: TestClient) -> None:
    auth = _auth(client)
    assert auth["organization"]["default_currency"] == "INR"

def _patch(client: TestClient, token: str, deal: dict[str, Any], **body: Any) -> Any:
    return client.patch(
        f"/api/v1/deals/{deal['id']}",
        json={"expected_revision": deal["revision"], **body},
        headers=_headers(token),
    )


def _correct(client: TestClient, token: str, deal: dict[str, Any], **body: Any) -> Any:
    return client.post(
        f"/api/v1/deals/{deal['id']}/amount-correction",
        json={"expected_revision": deal["revision"], **body},
        headers=_headers(token),
    )


def test_probability_override_changes_are_recorded_in_history(client: TestClient) -> None:
    token = _auth(client)["access_token"]
    deal = _deal(client, token, probability=35).json()
    deal = _patch(client, token, deal, probability=40).json()
    unchanged = _patch(client, token, deal, probability=40).json()
    assert unchanged["revision"] == deal["revision"]
    deal = _patch(client, token, deal, probability=None).json()
    deal = _stage(client, token, deal, stage="DISCOVERY", probability=60).json()
    # Moving stage resets an override; the reset itself is history.
    deal = _stage(client, token, deal, stage="PROPOSAL").json()
    deal = _stage(client, token, deal, stage="NEGOTIATION").json()

    events = _history(client, token, deal["id"])
    assert [
        (event["changes"], event["previous_probability"], event["new_probability"])
        for event in events
    ] == [
        (["CREATED"], None, 35),
        (["PROBABILITY"], 35, 40),
        (["PROBABILITY"], 40, None),
        (["STAGE", "PROBABILITY"], None, 60),
        (["STAGE", "PROBABILITY"], 60, None),
        (["STAGE"], None, None),
    ]
    assert not any(event["is_correction"] for event in events)


def test_probability_and_amount_change_together_write_one_event(client: TestClient) -> None:
    token = _auth(client)["access_token"]
    deal = _deal(client, token).json()
    _patch(client, token, deal, amount="1.00", probability=5, change_reason="Rescoped")
    events = _history(client, token, deal["id"])
    assert events[-1]["changes"] == ["AMOUNT", "PROBABILITY"]
    assert events[-1]["change_reason"] == "Rescoped"
    assert len(events) == 2


def test_won_deal_amount_is_locked_for_ordinary_edits(client: TestClient, db: Session) -> None:
    roles = _org_with_roles(client, db)
    deal = _deal(client, roles["owner"], amount="5000.00").json()
    won = _stage(client, roles["owner"], deal, stage="CLOSED_WON").json()
    before = _history(client, roles["owner"], won["id"])

    for role in ("owner", "admin", "member"):
        response = _patch(client, roles[role], won, amount="6000.00")
        assert response.status_code == 422
        assert response.json()["detail"] == (
            "The amount of a won deal is locked. An owner or admin can record a correction "
            "with a reason."
        )
    # Re-sending the same amount (any scale) is not a change, and other fields stay editable.
    same = _patch(client, roles["member"], won, amount="5000", name="Renamed").json()
    assert same["amount"] == "5000.00"
    assert same["name"] == "Renamed"
    assert _history(client, roles["owner"], won["id"]) == before
    stored = db.get(Deal, won["id"])
    assert stored is not None
    db.refresh(stored)
    assert stored.amount == Decimal("5000.00")

    lost = _deal(client, roles["owner"], amount="10.00").json()
    lost = _stage(client, roles["owner"], lost, stage="CLOSED_LOST", lost_reason="No fit").json()
    assert _patch(client, roles["member"], lost, amount="11.00").status_code == 200


def test_managers_correct_won_amounts_with_an_audited_reason(
    client: TestClient, db: Session
) -> None:
    roles = _org_with_roles(client, db)
    deal = _deal(client, roles["owner"], amount="5000.00").json()
    won = _stage(client, roles["owner"], deal, stage="CLOSED_WON").json()

    assert (
        _correct(client, roles["member"], won, amount="4500.00", reason="Typo").status_code == 403
    )
    assert _correct(client, roles["admin"], won, amount="4500.00").status_code == 422
    assert _correct(client, roles["admin"], won, amount="4500.00", reason="  ").status_code == 422
    assert _correct(client, roles["admin"], won, amount=4500.5, reason="x").status_code == 422
    same = _correct(client, roles["admin"], won, amount="5000.0", reason="No-op")
    assert same.status_code == 422
    stale = _correct(
        client, roles["admin"], {**won, "revision": 1}, amount="4500.00", reason="Typo"
    )
    assert stale.status_code == 409

    corrected = _correct(
        client, roles["admin"], won, amount="4500.00", reason="  Invoice was 4,500  "
    )
    assert corrected.status_code == 200, corrected.text
    body = corrected.json()
    assert body["amount"] == "4500.00"
    assert body["stage"] == "CLOSED_WON"
    assert body["revision"] == won["revision"] + 1
    assert body["closed_at"] == won["closed_at"]

    event = _history(client, roles["owner"], won["id"])[-1]
    assert event["is_correction"] is True
    assert event["changes"] == ["AMOUNT"]
    assert (event["previous_amount"], event["new_amount"]) == ("5000.00", "4500.00")
    assert event["change_reason"] == "Invoice was 4,500"
    assert event["changed_by_user_id"] == roles["admin_id"]

    owner_fix = _correct(client, roles["owner"], body, amount="4600.00", reason="Credit note")
    assert owner_fix.status_code == 200
    summary = client.get("/api/v1/pipeline/summary", headers=_headers(roles["member"])).json()
    assert summary["won"]["total_amount"] == "4600.00"


def test_amount_corrections_apply_only_to_won_deals_in_the_same_organization(
    client: TestClient,
) -> None:
    token = _auth(client)["access_token"]
    open_deal = _deal(client, token).json()
    response = _correct(client, token, open_deal, amount="1.00", reason="Fix")
    assert response.status_code == 422
    assert response.json()["detail"] == "Only won deals use amount corrections; use PATCH"
    lost = _stage(client, token, open_deal, stage="CLOSED_LOST", lost_reason="Gone").json()
    assert _correct(client, token, lost, amount="1.00", reason="Fix").status_code == 422

    won = _stage(client, token, _deal(client, token).json(), stage="CLOSED_WON").json()
    other = _auth(client, email="b@example.com", organization_name="Org B")["access_token"]
    assert _correct(client, other, won, amount="1.00", reason="Fix").status_code == 404
    assert client.post(f"/api/v1/deals/{won['id']}/amount-correction", json={}).status_code == 401


def test_correction_flag_is_constrained_to_won_events_with_a_reason(db: Session) -> None:
    organization = Organization(name="Raw", slug="raw-history")
    db.add(organization)
    db.commit()
    deal = Deal(
        organization_id=organization.id,
        name="Raw",
        amount=Decimal("1.00"),
        currency="INR",
        stage="QUALIFICATION",
        expected_close_date=date(2026, 12, 1),
        revision=1,
        stage_entered_at=datetime.now(UTC),
    )
    db.add(deal)
    db.commit()
    for overrides in (
        {"is_correction": True, "change_reason": "Fix"},
        {"previous_probability": 101},
        {"new_stage": "CLOSED_WON", "new_probability": 50},
    ):
        values: dict[str, Any] = {
            "organization_id": organization.id,
            "deal_id": deal.id,
            "previous_stage": "QUALIFICATION",
            "new_stage": "QUALIFICATION",
            "new_amount": Decimal("1.00"),
            "new_expected_close_date": date(2026, 12, 1),
        }
        values.update(overrides)
        db.add(DealStageEvent(**values))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()


def _won_deal(client: TestClient, roles: dict[str, Any]) -> dict[str, Any]:
    deal = _deal(client, roles["member"], amount="5000.00", probability=40).json()
    won = _stage(client, roles["member"], deal, stage="CLOSED_WON")
    assert won.status_code == 200  # every role can still win a deal
    return dict(won.json())


@pytest.mark.parametrize(
    "target", ["QUALIFICATION", "DISCOVERY", "PROPOSAL", "NEGOTIATION", "CLOSED_LOST"]
)
def test_members_cannot_move_a_won_deal_out_of_closed_won(
    client: TestClient, db: Session, target: str
) -> None:
    roles = _org_with_roles(client, db)
    won = _won_deal(client, roles)
    before = _history(client, roles["owner"], won["id"])
    body = {"lost_reason": "Cancelled"} if target == "CLOSED_LOST" else {}

    response = _stage(client, roles["member"], won, stage=target, **body)
    assert response.status_code == 403
    assert response.json()["detail"] == (
        "Only owners and admins can move a won deal to another stage"
    )
    current = client.get(f"/api/v1/deals/{won['id']}", headers=_headers(roles["owner"])).json()
    assert (current["stage"], current["revision"], current["amount"]) == (
        "CLOSED_WON",
        won["revision"],
        "5000.00",
    )
    assert current["closed_at"] == won["closed_at"]
    assert _history(client, roles["owner"], won["id"]) == before


@pytest.mark.parametrize("role", ["owner", "admin"])
def test_managers_reopen_won_deals_with_recorded_history(
    client: TestClient, db: Session, role: str
) -> None:
    roles = _org_with_roles(client, db)
    won = _won_deal(client, roles)
    reopened = _stage(
        client, roles[role], won, stage="NEGOTIATION", probability=60, change_reason="Re-scoped"
    )
    assert reopened.status_code == 200, reopened.text
    body = reopened.json()
    assert body["stage"] == "NEGOTIATION"
    assert body["closed_at"] is None
    assert body["effective_probability"] == 60
    assert body["revision"] == won["revision"] + 1

    event = _history(client, roles["owner"], won["id"])[-1]
    assert event["changes"] == ["STAGE", "PROBABILITY"]
    assert (event["previous_stage"], event["new_stage"]) == ("CLOSED_WON", "NEGOTIATION")
    assert (event["previous_probability"], event["new_probability"]) == (None, 60)
    assert event["change_reason"] == "Re-scoped"
    assert event["changed_by_user_id"] == roles[f"{role}_id"]
    assert event["is_correction"] is False

    # Once a manager has reopened it, the deal is open again for everyone.
    edited = _patch(client, roles["member"], body, amount="5500.00")
    assert edited.status_code == 200
    rewon = _stage(client, roles["member"], edited.json(), stage="CLOSED_WON").json()
    assert rewon["amount"] == "5500.00"
    assert _stage(client, roles["member"], rewon, stage="PROPOSAL").status_code == 403


@pytest.mark.parametrize("role", ["owner", "admin"])
def test_managers_can_mark_a_won_deal_lost_with_the_usual_rules(
    client: TestClient, db: Session, role: str
) -> None:
    roles = _org_with_roles(client, db)
    won = _won_deal(client, roles)
    assert _stage(client, roles[role], won, stage="CLOSED_LOST").status_code == 422
    assert _stage(client, roles[role], won, stage="DISCOVERY", lost_reason="x").status_code == 422
    lost = _stage(client, roles[role], won, stage="CLOSED_LOST", lost_reason="Contract voided")
    assert lost.status_code == 200
    assert lost.json()["lost_reason"] == "Contract voided"
    assert lost.json()["closed_at"] is not None
    event = _history(client, roles["owner"], won["id"])[-1]
    assert (event["previous_stage"], event["new_stage"]) == ("CLOSED_WON", "CLOSED_LOST")


def test_members_cannot_bypass_the_won_amount_lock(client: TestClient, db: Session) -> None:
    roles = _org_with_roles(client, db)
    won = _won_deal(client, roles)
    member = roles["member"]
    before = _history(client, roles["owner"], won["id"])

    attempts = [
        _patch(client, member, won, amount="9000.00"),
        _patch(client, member, won, stage="NEGOTIATION"),  # stage is not a PATCH field
        _patch(client, member, won, probability=50),
        _stage(client, member, won, stage="NEGOTIATION"),
        _stage(client, member, won, stage="CLOSED_LOST", lost_reason="Detour"),
        _correct(client, member, won, amount="9000.00", reason="Trust me"),
        client.post(
            f"/api/v1/deals/{won['id']}/stage",
            json={"stage": "PROPOSAL", "expected_revision": won["revision"], "role": "OWNER"},
            headers=_headers(member),
        ),
    ]
    assert [response.status_code for response in attempts] == [422, 422, 422, 403, 403, 403, 422]

    # Re-winning a won deal is a no-op and cannot carry other changes.
    assert _stage(client, member, won, stage="CLOSED_WON").json()["revision"] == won["revision"]
    assert _stage(client, member, won, stage="CLOSED_WON", lost_reason="x").status_code == 422

    current = client.get(f"/api/v1/deals/{won['id']}", headers=_headers(member)).json()
    assert (current["stage"], current["amount"], current["revision"]) == (
        "CLOSED_WON",
        "5000.00",
        won["revision"],
    )
    assert _history(client, roles["owner"], won["id"]) == before
    stored = db.get(Deal, won["id"])
    assert stored is not None
    db.refresh(stored)
    assert (stored.stage, stored.amount) == ("CLOSED_WON", Decimal("5000.00"))


def test_reopen_checks_tenant_and_revision_before_role(client: TestClient, db: Session) -> None:
    roles = _org_with_roles(client, db)
    won = _won_deal(client, roles)
    other_owner = _auth(client, email="b-owner@example.com", organization_name="Org B")
    other_member = _add_org_member(
        db,
        other_owner["organization"]["id"],
        email="b-member@example.com",
        role=MembershipRole.MEMBER,
    )
    # Another organization sees 404 whatever its role, never a 403 that confirms the deal.
    for token in (other_owner["access_token"], other_member):
        assert _stage(client, token, won, stage="NEGOTIATION").status_code == 404
    stale = {**won, "revision": won["revision"] - 1}
    assert _stage(client, roles["owner"], stale, stage="NEGOTIATION").status_code == 409
    assert _stage(client, roles["member"], stale, stage="NEGOTIATION").status_code == 409
    current = client.get(f"/api/v1/deals/{won['id']}", headers=_headers(roles["owner"])).json()
    assert current["stage"] == "CLOSED_WON"


def test_other_stage_transitions_are_unchanged_for_members(client: TestClient, db: Session) -> None:
    roles = _org_with_roles(client, db)
    member = roles["member"]
    deal = _deal(client, member).json()
    for stage in ("DISCOVERY", "QUALIFICATION", "NEGOTIATION"):
        deal = _stage(client, member, deal, stage=stage).json()
        assert deal["stage"] == stage
    lost = _stage(client, member, deal, stage="CLOSED_LOST", lost_reason="Budget").json()
    reopened = _stage(client, member, lost, stage="PROPOSAL")
    assert reopened.status_code == 200  # lost deals still reopen for every role
    won = _stage(client, member, reopened.json(), stage="CLOSED_WON").json()
    assert won["stage"] == "CLOSED_WON"
    assert _stage(client, member, deal, stage="CLOSED_WON").status_code == 409


def test_manager_reopen_and_amount_correction_coexist(client: TestClient, db: Session) -> None:
    roles = _org_with_roles(client, db)
    won = _won_deal(client, roles)
    corrected = _correct(client, roles["admin"], won, amount="4800.00", reason="Discount").json()
    reopened = _stage(client, roles["owner"], corrected, stage="PROPOSAL").json()
    rewon = _stage(client, roles["owner"], reopened, stage="CLOSED_WON").json()
    assert _correct(client, roles["owner"], reopened, amount="1.00", reason="x").status_code == 409
    final = _correct(client, roles["owner"], rewon, amount="4900.00", reason="Final invoice")
    assert final.status_code == 200
    events = _history(client, roles["owner"], won["id"])
    assert [(e["changes"], e["is_correction"]) for e in events] == [
        (["CREATED"], False),
        (["STAGE", "PROBABILITY"], False),
        (["AMOUNT"], True),
        (["STAGE"], False),
        (["STAGE"], False),
        (["AMOUNT"], True),
    ]


@pytest.mark.parametrize("role", ["owner", "admin", "member"])
def test_only_managers_create_deals_that_are_already_won(
    client: TestClient, db: Session, role: str
) -> None:
    roles = _org_with_roles(client, db)
    token = roles[role]
    lead = _create_lead(client, token, name="Won lead").json()
    response = _deal(client, token, stage="CLOSED_WON", amount="7000.00", lead_id=lead["id"])

    if role == "member":
        assert response.status_code == 403
        assert response.json()["detail"] == (
            "Only owners and admins can create a deal that is already won"
        )
        # Rejected before anything is written: no deal, no history, no lead conversion.
        assert client.get("/api/v1/deals", headers=_headers(token)).json()["total"] == 0
        assert db.scalars(select(DealStageEvent)).all() == []
        assert client.get(f"/api/v1/leads/{lead['id']}", headers=_headers(token)).json()[
            "status"
        ] == "NEW"
        summary = client.get("/api/v1/pipeline/summary", headers=_headers(token)).json()
        assert summary["won"] == {"count": 0, "total_amount": "0.00"}
    else:
        assert response.status_code == 201, response.text
        deal = response.json()
        assert (deal["stage"], deal["amount"], deal["effective_probability"]) == (
            "CLOSED_WON",
            "7000.00",
            100,
        )
        assert deal["closed_at"] is not None
        assert _history(client, token, deal["id"])[0]["new_stage"] == "CLOSED_WON"
        assert client.get(f"/api/v1/leads/{lead['id']}", headers=_headers(token)).json()[
            "status"
        ] == "CONVERTED"


@pytest.mark.parametrize("role", ["owner", "admin", "member"])
@pytest.mark.parametrize("stage", ["QUALIFICATION", "DISCOVERY", "PROPOSAL", "NEGOTIATION"])
def test_every_role_creates_deals_in_open_stages(
    client: TestClient, db: Session, role: str, stage: str
) -> None:
    roles = _org_with_roles(client, db)
    response = _deal(client, roles[role], stage=stage)
    assert response.status_code == 201, response.text
    assert response.json()["stage"] == stage


def test_member_won_creation_checks_role_before_other_validation(
    client: TestClient, db: Session
) -> None:
    roles = _org_with_roles(client, db)
    other = _auth(client, email="b@example.com", organization_name="Org B")
    foreign_lead = _create_lead(client, other["access_token"], name="Foreign").json()
    member = roles["member"]
    # 403 for the won stage, whatever else is wrong, so nothing about the lead leaks.
    assert _deal(client, member, stage="CLOSED_WON", lead_id=foreign_lead["id"]).status_code == 403
    assert _deal(client, member, stage="CLOSED_WON", probability=90).status_code == 403
    # Without the won stage, the existing rules still apply.
    assert _deal(client, member, lead_id=foreign_lead["id"]).status_code == 404
    assert _deal(client, roles["owner"], stage="CLOSED_WON", probability=90).status_code == 422
    assert (
        _deal(client, roles["owner"], stage="CLOSED_WON", lead_id=foreign_lead["id"]).status_code
        == 404
    )
    # An owner of another organization never sees this organization's deals.
    _deal(client, roles["admin"], stage="CLOSED_WON")
    assert client.get("/api/v1/deals", headers=_headers(other["access_token"])).json()[
        "total"
    ] == 0


@pytest.mark.parametrize("role", ["owner", "admin", "member"])
def test_only_managers_create_deals_that_are_already_lost(
    client: TestClient, db: Session, role: str
) -> None:
    roles = _org_with_roles(client, db)
    token = roles[role]
    lead = _create_lead(client, token, name="Lost lead").json()
    response = _deal(
        client, token, stage="CLOSED_LOST", lost_reason="Chose a competitor", lead_id=lead["id"]
    )

    if role == "member":
        assert response.status_code == 403
        assert response.json()["detail"] == (
            "Only owners and admins can create a deal that is already lost"
        )
        assert client.get("/api/v1/deals", headers=_headers(token)).json()["total"] == 0
        assert db.scalars(select(DealStageEvent)).all() == []
        assert client.get(f"/api/v1/leads/{lead['id']}", headers=_headers(token)).json()[
            "status"
        ] == "NEW"
    else:
        assert response.status_code == 201, response.text
        deal = response.json()
        assert (deal["stage"], deal["lost_reason"], deal["effective_probability"]) == (
            "CLOSED_LOST",
            "Chose a competitor",
            0,
        )
        assert deal["closed_at"] is not None
        assert _history(client, token, deal["id"])[0]["new_stage"] == "CLOSED_LOST"
        assert client.get(f"/api/v1/leads/{lead['id']}", headers=_headers(token)).json()[
            "status"
        ] == "CONVERTED"
        # Lost-deal validation is unchanged for managers.
        assert _deal(client, token, stage="CLOSED_LOST").status_code == 422
        with_probability = _deal(client, token, stage="CLOSED_LOST", lost_reason="x", probability=5)
        assert with_probability.status_code == 422


def test_member_lost_creation_checks_role_before_other_validation(
    client: TestClient, db: Session
) -> None:
    roles = _org_with_roles(client, db)
    other = _auth(client, email="b@example.com", organization_name="Org B")
    foreign_lead = _create_lead(client, other["access_token"], name="Foreign").json()
    member = roles["member"]
    # 403 before the lead lookup or lost-reason validation, so nothing leaks.
    assert _deal(
        client, member, stage="CLOSED_LOST", lost_reason="x", lead_id=foreign_lead["id"]
    ).status_code == 403
    assert _deal(client, member, stage="CLOSED_LOST").status_code == 403
    # Members still close deals as lost, and reopen them, through the stage endpoint.
    deal = _deal(client, member).json()
    lost = _stage(client, member, deal, stage="CLOSED_LOST", lost_reason="Budget")
    assert lost.status_code == 200
    assert _stage(client, member, lost.json(), stage="PROPOSAL").status_code == 200
    # Another organization never sees this organization's deals.
    _deal(client, roles["owner"], stage="CLOSED_LOST", lost_reason="Gone")
    assert client.get("/api/v1/deals", headers=_headers(other["access_token"])).json()[
        "total"
    ] == 0

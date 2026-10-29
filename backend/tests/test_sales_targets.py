from datetime import date
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.sales_target import SalesTarget
from app.schemas.sales_targets import month_end
from tests.conftest import TestingSessionLocal
from tests.test_agent_runtime import _headers
from tests.test_deals import _org_with_roles
from tests.test_leads import _auth

PATH = "/api/v1/sales-targets"


def _put(client: TestClient, token: str, **overrides: Any) -> Any:
    body: dict[str, Any] = {"period_start": "2026-11-01", "amount": "500000.00"}
    body.update(overrides)
    return client.put(PATH, json=body, headers=_headers(token))


def test_unauthenticated_target_requests_are_rejected(client: TestClient) -> None:
    assert client.get(PATH).status_code == 401
    assert client.put(PATH, json={}).status_code == 401


@pytest.mark.parametrize("role", ["owner", "admin"])
def test_managers_can_create_and_update_targets(
    client: TestClient, db: Session, role: str
) -> None:
    roles = _org_with_roles(client, db)
    created = _put(client, roles[role])
    assert created.status_code == 201
    target = created.json()
    assert target["period_start"] == "2026-11-01"
    assert target["period_end"] == "2026-11-30"
    assert target["amount"] == "500000.00"
    assert target["currency"] == "INR"
    assert target["owner_user_id"] is None
    assert target["created_by_user_id"] == roles[f"{role}_id"]

    updated = _put(client, roles[role], amount="650000.5")
    assert updated.status_code == 200
    assert updated.json()["id"] == target["id"]
    assert updated.json()["amount"] == "650000.50"
    assert db.scalar(select(SalesTarget.id).where(SalesTarget.id != target["id"])) is None


def test_members_can_view_but_not_change_targets(client: TestClient, db: Session) -> None:
    roles = _org_with_roles(client, db)
    _put(client, roles["owner"])
    denied = _put(client, roles["member"], amount="1.00")
    assert denied.status_code == 403
    own_target = _put(client, roles["member"], owner_user_id=roles["member_id"])
    assert own_target.status_code == 403
    listed = client.get(PATH, headers=_headers(roles["member"]))
    assert listed.status_code == 200
    assert listed.json()["total"] == 1
    assert listed.json()["items"][0]["amount"] == "500000.00"


def test_period_validation(client: TestClient) -> None:
    token = _auth(client)["access_token"]
    assert _put(client, token, period_start="2026-11-15").status_code == 422
    assert _put(client, token, period_end="2026-11-29").status_code == 422
    assert _put(client, token, period_end="2026-12-31").status_code == 422
    assert _put(client, token, period_start="2026-13-01").status_code == 422
    leap = _put(client, token, period_start="2028-02-01", period_end="2028-02-29")
    assert leap.status_code == 201
    assert leap.json()["period_end"] == "2028-02-29"
    assert _put(client, token, period_start="2027-02-01").json()["period_end"] == "2027-02-28"
    assert month_end(date(2026, 12, 1)) == date(2026, 12, 31)


def test_amount_and_currency_validation(client: TestClient) -> None:
    token = _auth(client)["access_token"]
    for amount in ("-1.00", "1.234", 99.5, "abc", "NaN"):
        assert _put(client, token, amount=amount).status_code == 422, amount
    assert _put(client, token, currency="USD").status_code == 422
    assert _put(client, token, currency="inr").status_code == 201
    assert _put(client, token, unknown=True).status_code == 422


def test_duplicate_targets_are_prevented_per_owner_and_period(
    client: TestClient, db: Session
) -> None:
    roles = _org_with_roles(client, db)
    token = roles["owner"]
    _put(client, token)
    _put(client, token, amount="2.00")
    _put(client, token, owner_user_id=roles["member_id"], amount="100.00")
    _put(client, token, owner_user_id=roles["member_id"], amount="150.00")
    _put(client, token, owner_user_id=roles["admin_id"], amount="200.00")
    _put(client, token, period_start="2026-12-01", amount="3.00")
    rows = list(db.scalars(select(SalesTarget)))
    assert len(rows) == 4
    keyed = {(row.owner_user_id, row.period_start.isoformat()): row.amount for row in rows}
    assert keyed[(None, "2026-11-01")] == Decimal("2.00")
    assert keyed[(roles["member_id"], "2026-11-01")] == Decimal("150.00")

    # The database rejects a duplicate even if the service check is bypassed.
    db.add(
        SalesTarget(
            organization_id=roles["org_id"],
            owner_user_id=None,
            period_start=date(2026, 11, 1),
            period_end=date(2026, 11, 30),
            amount=Decimal("9.00"),
            currency="INR",
        )
    )
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_target_owner_must_belong_to_the_organization(client: TestClient) -> None:
    org_a = _auth(client, email="a@example.com", organization_name="Org A")
    org_b = _auth(client, email="b@example.com", organization_name="Org B")
    foreign = _put(client, org_a["access_token"], owner_user_id=org_b["user"]["id"])
    assert foreign.status_code == 422
    assert _put(client, org_a["access_token"], owner_user_id="nobody").status_code == 422


def test_targets_are_isolated_and_filterable(client: TestClient, db: Session) -> None:
    roles = _org_with_roles(client, db)
    other = _auth(client, email="other@example.com", organization_name="Other")
    _put(client, roles["owner"], period_start="2026-10-01")
    _put(client, roles["owner"], period_start="2026-11-01")
    _put(client, roles["owner"], period_start="2026-11-01", owner_user_id=roles["member_id"])
    _put(client, other["access_token"], period_start="2026-11-01")

    def periods(token: str, **params: Any) -> list[tuple[str | None, str]]:
        response = client.get(PATH, params=params, headers=_headers(token))
        assert response.status_code == 200
        return [(item["owner_user_id"], item["period_start"]) for item in response.json()["items"]]

    assert periods(roles["owner"]) == [
        (None, "2026-10-01"),
        (None, "2026-11-01"),
        (roles["member_id"], "2026-11-01"),
    ]
    assert periods(roles["owner"], organization_only=True) == [
        (None, "2026-10-01"),
        (None, "2026-11-01"),
    ]
    assert periods(roles["owner"], owner_user_id=roles["member_id"]) == [
        (roles["member_id"], "2026-11-01")
    ]
    assert periods(roles["owner"], period_from="2026-11-01", period_to="2026-11-30") == [
        (None, "2026-11-01"),
        (roles["member_id"], "2026-11-01"),
    ]
    assert periods(other["access_token"]) == [(None, "2026-11-01")]
    bad = client.get(
        PATH,
        params={"period_from": "2026-12-01", "period_to": "2026-01-01"},
        headers=_headers(roles["owner"]),
    )
    assert bad.status_code == 422


def test_targets_persist_across_sessions(client: TestClient) -> None:
    token = _auth(client)["access_token"]
    target = _put(client, token, amount="123456789012.34").json()
    fresh = TestingSessionLocal()
    try:
        stored = fresh.get(SalesTarget, target["id"])
        assert stored is not None
        assert Decimal(stored.amount) == Decimal("123456789012.34")
        assert stored.period_end.isoformat() == "2026-11-30"
    finally:
        fresh.close()

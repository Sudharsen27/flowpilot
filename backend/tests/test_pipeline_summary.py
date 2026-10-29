from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.deal import Deal
from app.services.pipeline_service import PipelineService
from tests.test_agent_runtime import _headers
from tests.test_deals import _deal, _stage
from tests.test_leads import _auth

PATH = "/api/v1/pipeline/summary"


def _summary(client: TestClient, token: str, **params: Any) -> dict[str, Any]:
    response = client.get(PATH, params=params, headers=_headers(token))
    assert response.status_code == 200, response.text
    return dict(response.json())


def _by_stage(summary: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {row["stage"]: row for row in summary["by_stage"]}


def test_summary_requires_authentication(client: TestClient) -> None:
    assert client.get(PATH).status_code == 401


def test_empty_organization_reports_zeros(client: TestClient) -> None:
    token = _auth(client)["access_token"]
    summary = _summary(client, token)
    assert summary["currency"] == "INR"
    assert summary["open"] == {"count": 0, "total_amount": "0.00", "weighted_amount": "0.00"}
    assert summary["won"] == {"count": 0, "total_amount": "0.00"}
    assert summary["lost"] == {"count": 0, "total_amount": "0.00"}
    assert summary["overdue_open"] == {"count": 0, "total_amount": "0.00"}
    assert [row["stage"] for row in summary["by_stage"]] == [
        "QUALIFICATION",
        "DISCOVERY",
        "PROPOSAL",
        "NEGOTIATION",
        "CLOSED_WON",
        "CLOSED_LOST",
    ]
    assert [row["default_probability"] for row in summary["by_stage"]] == [10, 25, 50, 75, 100, 0]
    assert len(summary["won_by_month"]) == 6
    assert all(month["total_amount"] == "0.00" for month in summary["won_by_month"])
    assert summary["excluded_other_currency_count"] == 0


def test_totals_and_weighted_pipeline_are_exact(client: TestClient) -> None:
    token = _auth(client)["access_token"]
    future = (date.today() + timedelta(days=30)).isoformat()
    _deal(client, token, amount="1000.00", expected_close_date=future)
    _deal(
        client,
        token,
        amount="333.33",
        stage="DISCOVERY",
        probability=33,
        expected_close_date=future,
    )
    _deal(client, token, amount="0.10", stage="PROPOSAL", expected_close_date=future)
    _deal(
        client,
        token,
        amount="999999999999.99",
        stage="NEGOTIATION",
        expected_close_date=future,
    )
    summary = _summary(client, token)
    # 1000.00 + 333.33 + 0.10 + 999999999999.99
    assert summary["open"]["total_amount"] == "1000000001333.42"
    # Each deal rounds once, half-up to the cent: 100.00 + 110.00 (109.9989) + 0.05
    # + 749999999999.99 (749999999999.9925). A float sum drifts at this magnitude.
    assert summary["open"]["weighted_amount"] == "750000000210.04"
    assert summary["open"]["count"] == 4
    stages = _by_stage(summary)
    assert stages["DISCOVERY"]["weighted_amount"] == "110.00"
    assert stages["NEGOTIATION"]["total_amount"] == "999999999999.99"
    assert stages["NEGOTIATION"]["weighted_amount"] == "749999999999.99"
    assert stages["PROPOSAL"]["weighted_amount"] == "0.05"


def test_won_lost_overdue_and_monthly_buckets(client: TestClient) -> None:
    token = _auth(client)["access_token"]
    past = (date.today() - timedelta(days=5)).isoformat()
    future = (date.today() + timedelta(days=5)).isoformat()
    _deal(client, token, amount="250.50", expected_close_date=past)
    _deal(client, token, amount="100.00", expected_close_date=future)
    won = _deal(client, token, amount="1200.00", expected_close_date=future).json()
    _stage(client, token, won, stage="CLOSED_WON")
    _deal(
        client,
        token,
        amount="75.25",
        stage="CLOSED_LOST",
        lost_reason="No budget",
        expected_close_date=past,
    )
    summary = _summary(client, token, months=3)
    assert summary["won"] == {"count": 1, "total_amount": "1200.00"}
    assert summary["lost"] == {"count": 1, "total_amount": "75.25"}
    # Closed deals are never overdue, even with a past expected close date.
    assert summary["overdue_open"] == {"count": 1, "total_amount": "250.50"}
    assert summary["open"]["count"] == 2
    months = summary["won_by_month"]
    assert len(months) == 3
    assert months[-1]["month"] == date.today().replace(day=1).isoformat()
    assert months[-1] == {
        "month": date.today().replace(day=1).isoformat(),
        "count": 1,
        "total_amount": "1200.00",
    }
    assert months[0]["total_amount"] == "0.00"


def test_month_window_is_zero_filled_and_bounded(client: TestClient, db: Session) -> None:
    auth = _auth(client)
    org_id = auth["organization"]["id"]
    now = datetime(2026, 3, 15, 12, tzinfo=UTC)
    for closed_at, amount in (
        (datetime(2026, 3, 2, tzinfo=UTC), "10.00"),
        (datetime(2026, 1, 31, 23, 59, tzinfo=UTC), "20.00"),
        (datetime(2025, 9, 1, tzinfo=UTC), "40.00"),  # outside a 4-month window
    ):
        db.add(
            Deal(
                organization_id=org_id,
                name="Won",
                amount=Decimal(amount),
                currency="INR",
                stage="CLOSED_WON",
                expected_close_date=closed_at.date(),
                closed_at=closed_at,
                revision=1,
                stage_entered_at=closed_at,
            )
        )
    db.commit()
    summary = PipelineService(db).summary(org_id, months=4, now=now)
    assert [(m.month.isoformat(), m.count, m.total_amount) for m in summary.won_by_month] == [
        ("2025-12-01", 0, Decimal("0.00")),
        ("2026-01-01", 1, Decimal("20.00")),
        ("2026-02-01", 0, Decimal("0.00")),
        ("2026-03-01", 1, Decimal("10.00")),
    ]
    # All-time won totals still include the deal outside the window.
    assert summary.won.total_amount == Decimal("70.00")


def test_other_currency_deals_are_excluded_not_mixed(client: TestClient, db: Session) -> None:
    auth = _auth(client)
    token = auth["access_token"]
    _deal(client, token, amount="100.00")
    db.add(
        Deal(
            organization_id=auth["organization"]["id"],
            name="Legacy USD",
            amount=Decimal("5000.00"),
            currency="USD",
            stage="QUALIFICATION",
            expected_close_date=date(2026, 12, 1),
            revision=1,
            stage_entered_at=datetime.now(UTC),
        )
    )
    db.commit()
    summary = _summary(client, token)
    assert summary["open"]["total_amount"] == "100.00"
    assert summary["excluded_other_currency_count"] == 1


def test_months_parameter_is_validated(client: TestClient) -> None:
    token = _auth(client)["access_token"]
    for months in (0, 25, "x"):
        response = client.get(PATH, params={"months": months}, headers=_headers(token))
        assert response.status_code == 422
    assert len(_summary(client, token, months=24)["won_by_month"]) == 24


def test_summary_is_organization_scoped_and_read_only(client: TestClient, db: Session) -> None:
    org_a = _auth(client, email="a@example.com", organization_name="Org A")
    org_b = _auth(client, email="b@example.com", organization_name="Org B")
    deal = _deal(client, org_a["access_token"], amount="999.99").json()
    assert _summary(client, org_a["access_token"])["open"]["total_amount"] == "999.99"
    assert _summary(client, org_b["access_token"])["open"]["count"] == 0
    stored = db.get(Deal, deal["id"])
    assert stored is not None
    assert stored.revision == 1
    assert stored.updated_at is not None

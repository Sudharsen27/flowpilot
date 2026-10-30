import random
from datetime import UTC, date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.orm import Session

from app.core.exceptions import UnprocessableError
from app.models.deal import Deal, effective_probability
from app.schemas.pipeline import ForecastGranularity, PipelineForecast
from app.services.pipeline_service import PipelineService
from tests.test_agent_runtime import _headers
from tests.test_deals import _deal, _org_with_roles
from tests.test_leads import _auth

PATH = "/api/v1/pipeline/forecast"
NOW = datetime(2026, 3, 15, 12, tzinfo=UTC)
BASE_ASSUMPTIONS = [
    "STAGE_PROBABILITY_WEIGHTING",
    "NO_HISTORICAL_WIN_RATES",
    "EXPECTED_CLOSE_DATE_PERIODS",
    "UTC_PERIODS",
    "SINGLE_CURRENCY",
    "WON_AMOUNT_CURRENT_VALUE",
    "ORGANIZATION_TARGETS_ONLY",
]


def _forecast(client: TestClient, token: str, **params: Any) -> dict[str, Any]:
    response = client.get(PATH, params=params, headers=_headers(token))
    assert response.status_code == 200, response.text
    return dict(response.json())


def _row(organization_id: str, amount: str, **overrides: Any) -> Deal:
    stage = overrides.get("stage", "QUALIFICATION")
    closed_at = overrides.pop("closed_at", None)
    if stage in ("CLOSED_WON", "CLOSED_LOST") and closed_at is None:
        closed_at = NOW
    values: dict[str, Any] = {
        "organization_id": organization_id,
        "name": "Deal",
        "amount": Decimal(amount),
        "currency": "INR",
        "stage": stage,
        "expected_close_date": date(2026, 4, 10),
        "closed_at": closed_at,
        "lost_reason": "No budget" if stage == "CLOSED_LOST" else None,
        "revision": 1,
        "stage_entered_at": NOW,
    }
    values.update(overrides)
    return Deal(**values)


def _org(client: TestClient) -> tuple[str, str]:
    auth = _auth(client)
    return auth["access_token"], auth["organization"]["id"]


def _run(db: Session, org_id: str, granularity: str = "month", **kwargs: Any) -> PipelineForecast:
    return PipelineService(db).forecast(
        org_id, granularity=ForecastGranularity(granularity), now=kwargs.pop("now", NOW), **kwargs
    )


def _sum(values: list[Decimal]) -> Decimal:
    return sum(values, Decimal("0.00"))


def _assert_reconciles(forecast: PipelineForecast) -> None:
    """Every open deal lands in exactly one bucket, and the parts add up exactly."""
    buckets = [forecast.past_due, *(p.open for p in forecast.periods), forecast.beyond_horizon]
    total = forecast.open_pipeline
    assert sum(b.count for b in buckets) == total.count
    assert _sum([b.total_amount for b in buckets]) == total.total_amount
    assert _sum([b.weighted_amount for b in buckets]) == total.weighted_amount
    assert sum(b.override_count for b in buckets) == total.override_count
    for period in forecast.periods:
        assert period.projected_amount == period.won.total_amount + period.open.weighted_amount
    assert forecast.won_in_horizon.total_amount == _sum(
        [p.won.total_amount for p in forecast.periods]
    )
    assert forecast.projected_in_horizon_amount == _sum(
        [p.projected_amount for p in forecast.periods]
    )


def test_forecast_requires_authentication(client: TestClient) -> None:
    assert client.get(PATH).status_code == 401


def test_empty_organization_defaults_to_six_months(client: TestClient) -> None:
    token, _ = _org(client)
    forecast = _forecast(client, token)
    assert forecast["currency"] == "INR"
    assert forecast["granularity"] == "month"
    assert forecast["method"] == "STAGE_PROBABILITY_WEIGHTED"
    assert forecast["rounding"] == "PER_DEAL_HALF_UP_CENTS"
    assert len(forecast["periods"]) == 6
    first_month = date.today().replace(day=1)
    assert forecast["horizon_start"] == first_month.isoformat()
    assert forecast["periods"][0]["label"] == f"{first_month.year}-{first_month.month:02d}"
    zero_categories = [
        {"category": category, "count": 0, "total_amount": "0.00", "weighted_amount": "0.00"}
        for category in ("PIPELINE", "BEST_CASE", "COMMIT")
    ]
    zero_open = {
        "count": 0,
        "total_amount": "0.00",
        "weighted_amount": "0.00",
        "override_count": 0,
        "category_totals": zero_categories,
    }
    assert all(period["open"] == zero_open for period in forecast["periods"])
    assert all(period["projected_amount"] == "0.00" for period in forecast["periods"])
    assert forecast["past_due"] == {**zero_open, "oldest_expected_close_date": None}
    assert forecast["beyond_horizon"] == zero_open
    assert forecast["open_pipeline"] == zero_open
    assert forecast["won_in_horizon"] == {"count": 0, "total_amount": "0.00"}
    assert forecast["in_horizon_open"] == zero_open
    assert forecast["commit_scenario_amount"] == "0.00"
    assert forecast["best_case_scenario_amount"] == "0.00"
    # No targets are set, so every month of the horizon is reported as missing one.
    assert [a["code"] for a in forecast["assumptions"]] == [
        *BASE_ASSUMPTIONS,
        "TARGETS_INCOMPLETE",
    ]
    assert [p["default_probability"] for p in forecast["stage_probabilities"]] == [
        10,
        25,
        50,
        75,
        100,
        0,
    ]
    assert forecast["excluded_other_currency_count"] == 0
    assert len(_forecast(client, token, granularity="quarter")["periods"]) == 4


def test_month_boundaries_past_due_and_beyond_horizon(client: TestClient, db: Session) -> None:
    _, org_id = _org(client)
    db.add_all(
        [
            _row(org_id, "1.00", expected_close_date=date(2026, 3, 14)),  # past due
            _row(org_id, "2.00", expected_close_date=date(2026, 1, 2)),  # past due, oldest
            _row(org_id, "10.00", expected_close_date=date(2026, 3, 15)),  # today: March
            _row(org_id, "20.00", expected_close_date=date(2026, 3, 31)),
            _row(org_id, "40.00", expected_close_date=date(2026, 4, 1)),
            _row(org_id, "80.00", expected_close_date=date(2026, 8, 31)),  # last period
            _row(org_id, "160.00", expected_close_date=date(2026, 9, 1)),  # beyond
            # Won revenue is bucketed by closed_at, never by expected close date.
            _row(
                org_id,
                "1000.00",
                stage="CLOSED_WON",
                closed_at=datetime(2026, 2, 28, 23, 59, 59, tzinfo=UTC),
            ),
            _row(
                org_id,
                "2000.00",
                stage="CLOSED_WON",
                closed_at=datetime(2026, 3, 1, tzinfo=UTC),
                expected_close_date=date(2026, 7, 1),
            ),
            _row(
                org_id,
                "4000.00",
                stage="CLOSED_WON",
                closed_at=datetime(2026, 8, 31, 23, 59, 59, tzinfo=UTC),
            ),
            _row(org_id, "8000.00", stage="CLOSED_WON", closed_at=datetime(2026, 9, 1, tzinfo=UTC)),
            _row(org_id, "16000.00", stage="CLOSED_LOST"),  # never forecast
        ]
    )
    db.commit()

    forecast = _run(db, org_id)
    assert forecast.horizon_start == date(2026, 3, 1)
    assert forecast.horizon_end == date(2026, 8, 31)
    assert [(p.label, p.period_start, p.period_end) for p in forecast.periods][:2] == [
        ("2026-03", date(2026, 3, 1), date(2026, 3, 31)),
        ("2026-04", date(2026, 4, 1), date(2026, 4, 30)),
    ]
    by_label = {p.label: p for p in forecast.periods}
    assert by_label["2026-03"].open.total_amount == Decimal("30.00")
    assert by_label["2026-03"].open.weighted_amount == Decimal("3.00")
    assert by_label["2026-03"].won.total_amount == Decimal("2000.00")
    assert by_label["2026-03"].projected_amount == Decimal("2003.00")
    assert by_label["2026-04"].open.total_amount == Decimal("40.00")
    assert by_label["2026-08"].open.total_amount == Decimal("80.00")
    assert by_label["2026-08"].won.total_amount == Decimal("4000.00")
    assert by_label["2026-07"].won.count == 0
    assert forecast.past_due.count == 2
    assert forecast.past_due.total_amount == Decimal("3.00")
    assert forecast.past_due.oldest_expected_close_date == date(2026, 1, 2)
    assert forecast.beyond_horizon.total_amount == Decimal("160.00")
    assert forecast.open_pipeline.count == 7
    assert forecast.open_pipeline.total_amount == Decimal("313.00")
    assert forecast.won_in_horizon.count == 2
    assert forecast.won_in_horizon.total_amount == Decimal("6000.00")
    codes = [a.code for a in forecast.assumptions]
    assert "PAST_DUE_SEPARATED" in codes
    assert "OTHER_CURRENCY_EXCLUDED" not in codes
    _assert_reconciles(forecast)


def test_quarter_boundaries_and_year_rollover(client: TestClient, db: Session) -> None:
    _, org_id = _org(client)
    db.add_all(
        [
            _row(org_id, "1.00", expected_close_date=date(2026, 3, 31)),
            _row(org_id, "2.00", expected_close_date=date(2026, 4, 1)),
            _row(org_id, "4.00", expected_close_date=date(2026, 6, 30)),
            _row(org_id, "8.00", expected_close_date=date(2026, 7, 1)),
            _row(
                org_id,
                "100.00",
                stage="CLOSED_WON",
                closed_at=datetime(2026, 3, 31, 23, 59, tzinfo=UTC),
            ),
            _row(org_id, "200.00", stage="CLOSED_WON", closed_at=datetime(2026, 4, 1, tzinfo=UTC)),
        ]
    )
    db.commit()

    end_of_q1 = datetime(2026, 3, 31, 23, 59, 59, tzinfo=UTC)
    forecast = _run(db, org_id, "quarter", periods=2, now=end_of_q1)
    assert [(p.label, p.period_start, p.period_end) for p in forecast.periods] == [
        ("2026-Q1", date(2026, 1, 1), date(2026, 3, 31)),
        ("2026-Q2", date(2026, 4, 1), date(2026, 6, 30)),
    ]
    q1, q2 = forecast.periods
    assert (q1.open.total_amount, q1.won.total_amount) == (Decimal("1.00"), Decimal("100.00"))
    assert (q2.open.total_amount, q2.won.total_amount) == (Decimal("6.00"), Decimal("200.00"))
    assert forecast.beyond_horizon.total_amount == Decimal("8.00")
    assert forecast.past_due.count == 0
    _assert_reconciles(forecast)

    # A new quarter starts at midnight UTC: Q1's last-day deal is now past due.
    start_of_q2 = datetime(2026, 4, 1, tzinfo=UTC)
    moved = _run(db, org_id, "quarter", periods=1, now=start_of_q2)
    assert moved.periods[0].label == "2026-Q2"
    assert moved.past_due.total_amount == Decimal("1.00")
    assert moved.periods[0].won.total_amount == Decimal("200.00")

    rollover = _run(db, org_id, "quarter", periods=3, now=datetime(2026, 11, 10, tzinfo=UTC))
    assert [p.label for p in rollover.periods] == ["2026-Q4", "2027-Q1", "2027-Q2"]
    assert rollover.horizon_end == date(2027, 6, 30)
    december = _run(db, org_id, periods=2, now=datetime(2026, 12, 31, 23, 0, tzinfo=UTC))
    assert [p.label for p in december.periods] == ["2026-12", "2027-01"]


def test_as_of_converts_to_utc_before_bucketing(client: TestClient, db: Session) -> None:
    _, org_id = _org(client)
    db.add(_row(org_id, "5.00", expected_close_date=date(2026, 3, 31)))
    db.commit()
    # 1 April 02:00 in India is still 31 March in UTC.
    ist = datetime(2026, 4, 1, 2, 0, tzinfo=ZoneInfo("Asia/Kolkata"))
    forecast = _run(db, org_id, periods=1, now=ist)
    assert forecast.as_of == datetime(2026, 3, 31, 20, 30, tzinfo=UTC)
    assert forecast.periods[0].label == "2026-03"
    assert forecast.periods[0].open.total_amount == Decimal("5.00")


def test_per_deal_rounding_reconciles_with_summary(client: TestClient, db: Session) -> None:
    _, org_id = _org(client)
    # Each 0.05 at 10% is 0.005 -> 0.01. Rounding the stage sum (0.015) would give 0.02.
    db.add_all([_row(org_id, "0.05", expected_close_date=date(2026, 3 + i, 20)) for i in range(3)])
    db.commit()
    forecast = _run(db, org_id)
    assert forecast.open_pipeline.weighted_amount == Decimal("0.03")
    assert [p.open.weighted_amount for p in forecast.periods[:3]] == [Decimal("0.01")] * 3
    summary = PipelineService(db).summary(org_id, months=6, now=NOW)
    assert summary.open.weighted_amount == Decimal("0.03")
    assert summary.by_stage[0].weighted_amount == Decimal("0.03")


def test_randomized_deals_match_a_per_deal_decimal_reference(
    client: TestClient, db: Session
) -> None:
    _, org_id = _org(client)
    rng = random.Random(8_2026)
    stages = ["QUALIFICATION", "DISCOVERY", "PROPOSAL", "NEGOTIATION"]
    rows = []
    for _ in range(300):
        stage = rng.choice(stages)
        rows.append(
            _row(
                org_id,
                f"{rng.randint(0, 10**9)}.{rng.randint(0, 99):02d}",
                stage=stage,
                probability=rng.choice([None, None, rng.randint(0, 100)]),
                expected_close_date=date(2026, 1, 1) + timedelta(days=rng.randint(0, 500)),
            )
        )
    db.add_all(rows)
    db.commit()

    def weighted(deal: Deal) -> Decimal:
        value = deal.amount * effective_probability(deal.stage, deal.probability) / 100
        return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    forecast = _run(db, org_id, periods=12)
    _assert_reconciles(forecast)
    assert forecast.open_pipeline.count == 300
    assert forecast.open_pipeline.total_amount == _sum([d.amount for d in rows])
    assert forecast.open_pipeline.weighted_amount == _sum([weighted(d) for d in rows])
    assert forecast.open_pipeline.override_count == sum(d.probability is not None for d in rows)
    past_due = [d for d in rows if d.expected_close_date < NOW.date()]
    assert forecast.past_due.weighted_amount == _sum([weighted(d) for d in past_due])
    april = [d for d in rows if d.expected_close_date.replace(day=1) == date(2026, 4, 1)]
    assert forecast.periods[1].open.weighted_amount == _sum([weighted(d) for d in april])

    summary = PipelineService(db).summary(org_id, months=1, now=NOW)
    assert summary.open.weighted_amount == forecast.open_pipeline.weighted_amount
    assert _sum([s.weighted_amount for s in summary.by_stage[:4]]) == summary.open.weighted_amount


def test_maximum_amounts_and_overrides_are_exact(client: TestClient) -> None:
    token, _ = _org(client)
    close = (date.today().replace(day=1) + timedelta(days=40)).isoformat()
    _deal(client, token, amount="999999999999.99", stage="NEGOTIATION", expected_close_date=close)
    _deal(client, token, amount="333.33", probability=33, expected_close_date=close)
    forecast = _forecast(client, token)
    # 749999999999.9925 -> .99 and 109.9989 -> 110.00, each rounded once per deal.
    assert forecast["open_pipeline"]["total_amount"] == "1000000000333.32"
    assert forecast["open_pipeline"]["weighted_amount"] == "750000000109.99"
    assert forecast["open_pipeline"]["override_count"] == 1
    overrides = [a for a in forecast["assumptions"] if a["code"] == "PROBABILITY_OVERRIDES"]
    assert overrides and overrides[0]["detail"].startswith("1 open deal")


def test_other_currency_deals_are_excluded_not_converted(client: TestClient, db: Session) -> None:
    token, org_id = _org(client)
    db.add_all(
        [
            _row(org_id, "100.00"),
            _row(org_id, "5000.00", currency="USD"),
            _row(org_id, "7000.00", currency="USD", stage="CLOSED_WON"),
        ]
    )
    db.commit()
    forecast = _run(db, org_id)
    assert forecast.open_pipeline.total_amount == Decimal("100.00")
    assert forecast.won_in_horizon.count == 0
    assert forecast.excluded_other_currency_count == 2
    assert "OTHER_CURRENCY_EXCLUDED" in [a.code for a in forecast.assumptions]


@pytest.mark.parametrize(
    "params",
    [
        {"granularity": "week"},
        {"periods": 0},
        {"periods": 25},
        {"periods": "x"},
        {"granularity": "quarter", "periods": 9},
    ],
)
def test_parameters_are_validated(client: TestClient, params: dict[str, Any]) -> None:
    token, _ = _org(client)
    response = client.get(PATH, params=params, headers=_headers(token))
    assert response.status_code == 422


def test_maximum_horizons_are_allowed(client: TestClient, db: Session) -> None:
    token, org_id = _org(client)
    assert len(_forecast(client, token, periods=24)["periods"]) == 24
    assert len(_forecast(client, token, granularity="quarter", periods=8)["periods"]) == 8
    with pytest.raises(UnprocessableError):
        _run(db, org_id, "quarter", periods=9)


def test_every_role_can_read_and_organizations_are_isolated(
    client: TestClient, db: Session
) -> None:
    roles = _org_with_roles(client, db)
    deal = _deal(client, roles["owner"], amount="999.99").json()
    for role in ("owner", "admin", "member"):
        assert _forecast(client, roles[role])["open_pipeline"]["total_amount"] == "999.99"

    other = _auth(client, email="other@example.com", organization_name="Org B")
    isolated = _forecast(client, other["access_token"])
    assert isolated["open_pipeline"]["count"] == 0
    assert isolated["excluded_other_currency_count"] == 0

    stored = db.get(Deal, deal["id"])
    assert stored is not None
    assert stored.revision == 1  # read-only


def test_query_count_does_not_grow_with_deals(client: TestClient, db: Session) -> None:
    _, org_id = _org(client)
    statements: list[str] = []

    def count(*args: Any) -> None:
        statements.append(args[2])

    def run() -> int:
        db.expire_all()
        statements.clear()
        engine = db.get_bind()
        event.listen(engine, "before_cursor_execute", count)
        try:
            _run(db, org_id, periods=12)
            PipelineService(db).summary(org_id, months=12, now=NOW)
        finally:
            event.remove(engine, "before_cursor_execute", count)
        return len(statements)

    db.add(_row(org_id, "1.00"))
    db.commit()
    few = run()
    db.add_all([_row(org_id, "1.00", stage="CLOSED_WON") for _ in range(50)])
    db.add_all([_row(org_id, "1.00") for _ in range(50)])
    db.commit()
    assert run() == few
    # The forecast's targets query is the eighth.
    assert few <= 8

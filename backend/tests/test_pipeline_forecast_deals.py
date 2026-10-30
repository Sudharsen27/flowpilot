"""Forecast category drill-down: the open deals behind each category total, selected exactly
as the forecast buckets them, so every page of deals reconciles with category_totals."""

import random
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.orm import Session

from app.core.exceptions import UnprocessableError
from app.models.deal import Deal, ForecastCategory, effective_probability
from app.schemas.pipeline import (
    ForecastCategoryDeals,
    ForecastGranularity,
    PipelineForecast,
    PipelineWeightedTotals,
)
from app.services.pipeline_service import PipelineService
from tests.test_agent_runtime import _headers
from tests.test_deals import _deal, _org_with_roles
from tests.test_leads import _auth
from tests.test_pipeline_forecast import NOW, _forecast, _org, _row, _run, _sum
from tests.test_pipeline_forecast_categories import CATEGORIES, _seed_mixed

PATH = "/api/v1/pipeline/forecast/deals"


def _drill(
    db: Session,
    org_id: str,
    category: str,
    granularity: str = "month",
    *,
    limit: int = 100,
    offset: int = 0,
    **kwargs: Any,
) -> ForecastCategoryDeals:
    return PipelineService(db).forecast_deals(
        org_id,
        category=ForecastCategory(category),
        granularity=ForecastGranularity(granularity),
        limit=limit,
        offset=offset,
        now=kwargs.pop("now", NOW),
        **kwargs,
    )


def _get(client: TestClient, token: str, **params: Any) -> Any:
    return client.get(PATH, params=params, headers=_headers(token))


def _totals(drill: ForecastCategoryDeals) -> tuple[int, Decimal, Decimal]:
    return drill.totals.count, drill.totals.total_amount, drill.totals.weighted_amount


def _category(totals: Any, category: str) -> tuple[int, Decimal, Decimal]:
    row = next(r for r in totals.category_totals if r.category.value == category)
    return row.count, row.total_amount, row.weighted_amount


def _assert_items_sum_to_totals(drill: ForecastCategoryDeals) -> None:
    assert drill.total == drill.totals.count == len(drill.items)
    assert _sum([item.amount for item in drill.items]) == drill.totals.total_amount
    assert _sum([item.weighted_amount for item in drill.items]) == drill.totals.weighted_amount


def _assert_drill_down_matches(
    db: Session, org_id: str, forecast: PipelineForecast, granularity: str, periods: int
) -> None:
    """Each category's deals, per period and for the whole horizon, are exactly the
    forecast's category totals; and they never overlap between periods."""
    for category in CATEGORIES:
        seen: set[str] = set()
        for period in forecast.periods:
            drill = _drill(
                db,
                org_id,
                category,
                granularity,
                periods=periods,
                period_start=period.period_start,
            )
            assert _totals(drill) == _category(period.open, category)
            assert (drill.range_start, drill.range_end) == (period.period_start, period.period_end)
            _assert_items_sum_to_totals(drill)
            for item in drill.items:
                assert item.period_start == period.period_start
                assert period.period_start <= item.expected_close_date <= period.period_end
                assert item.forecast_category.value == category
            ids = {item.id for item in drill.items}
            assert not ids & seen
            seen |= ids
        horizon = _drill(db, org_id, category, granularity, periods=periods)
        assert _totals(horizon) == _category(forecast.in_horizon_open, category)
        assert {item.id for item in horizon.items} == seen
        _assert_items_sum_to_totals(horizon)


def test_drill_down_requires_authentication(client: TestClient) -> None:
    assert client.get(PATH, params={"category": "COMMIT"}).status_code == 401


@pytest.mark.parametrize(
    "params",
    [
        {},
        {"category": "CLOSED"},
        {"category": "commit"},
        {"category": "COMMIT", "limit": 0},
        {"category": "COMMIT", "limit": 101},
        {"category": "COMMIT", "offset": -1},
        {"category": "COMMIT", "periods": 0},
        {"category": "COMMIT", "periods": 25},
        {"category": "COMMIT", "granularity": "quarter", "periods": 9},
        {"category": "COMMIT", "granularity": "week"},
        {"category": "COMMIT", "period_start": "not-a-date"},
    ],
)
def test_invalid_parameters_are_rejected(client: TestClient, params: dict[str, Any]) -> None:
    token, _ = _org(client)
    assert _get(client, token, **params).status_code == 422


def test_period_start_must_start_a_period_in_the_horizon(client: TestClient, db: Session) -> None:
    token, org_id = _org(client)
    service = PipelineService(db)
    for granularity, period_start in [
        ("month", date(2026, 3, 15)),  # inside a period, not its start
        ("month", date(2026, 2, 1)),  # before the horizon
        ("month", date(2026, 6, 1)),  # after a three-month horizon
        ("quarter", date(2026, 2, 1)),  # a month start that is not a quarter start
        ("quarter", date(2026, 7, 1)),  # the quarter after a one-quarter horizon
    ]:
        with pytest.raises(UnprocessableError, match="period_start"):
            service.forecast_deals(
                org_id,
                category=ForecastCategory.COMMIT,
                granularity=ForecastGranularity(granularity),
                periods=3 if granularity == "month" else 1,
                period_start=period_start,
                limit=20,
                offset=0,
                now=NOW,
            )
    response = _get(client, token, category="COMMIT", period_start="1999-01-01")
    assert response.status_code == 422
    assert "period_start" in response.json()["detail"]


def test_drill_down_reconciles_with_category_totals_by_month(
    client: TestClient, db: Session
) -> None:
    _, org_id = _org(client)
    _seed_mixed(db, org_id)
    forecast = _run(db, org_id, "month", periods=3)
    _assert_drill_down_matches(db, org_id, forecast, "month", 3)

    names = {
        category: sorted(item.amount for item in _drill(db, org_id, category, periods=3).items)
        for category in CATEGORIES
    }
    # Past-due (7.00, 9.00), beyond-horizon (11.00, 13.00), won and lost deals with a
    # stale category are absent; the deal stored without a category reads as PIPELINE.
    assert names == {
        "PIPELINE": [Decimal("50.00"), Decimal("400.00")],
        "BEST_CASE": [Decimal("200.00")],
        "COMMIT": [Decimal("100.00"), Decimal("333.33"), Decimal("1000.00")],
    }


def test_drill_down_reconciles_with_category_totals_by_quarter(
    client: TestClient, db: Session
) -> None:
    _, org_id = _org(client)
    _seed_mixed(db, org_id)
    for periods in (1, 2, 8):
        forecast = _run(db, org_id, "quarter", periods=periods)
        _assert_drill_down_matches(db, org_id, forecast, "quarter", periods)
    # One quarter (Jan to Mar) ends before April: only March deals are in it.
    first = _drill(db, org_id, "COMMIT", "quarter", periods=1)
    assert [item.amount for item in first.items] == [Decimal("100.00")]
    assert (first.range_start, first.range_end) == (date(2026, 1, 1), date(2026, 3, 31))


def test_commit_and_best_case_deals_rebuild_the_scenarios(client: TestClient, db: Session) -> None:
    _, org_id = _org(client)
    _seed_mixed(db, org_id)
    for granularity, periods in (("month", 3), ("month", 24), ("quarter", 4)):
        forecast = _run(db, org_id, granularity, periods=periods)
        won = forecast.won_in_horizon.total_amount
        commit = _drill(db, org_id, "COMMIT", granularity, periods=periods).totals.total_amount
        best = _drill(db, org_id, "BEST_CASE", granularity, periods=periods).totals.total_amount
        assert forecast.commit_scenario_amount == won + commit
        assert forecast.best_case_scenario_amount == won + commit + best


def test_other_currencies_closed_and_out_of_range_deals_are_excluded(
    client: TestClient, db: Session
) -> None:
    _, org_id = _org(client)
    db.add_all(
        [
            _row(org_id, "1.00", name="in", forecast_category="COMMIT"),
            _row(org_id, "2.00", name="usd", currency="USD", forecast_category="COMMIT"),
            _row(org_id, "3.00", name="won", stage="CLOSED_WON", forecast_category="COMMIT"),
            _row(org_id, "4.00", name="lost", stage="CLOSED_LOST", forecast_category="COMMIT"),
            _row(
                org_id,
                "5.00",
                name="yesterday",
                forecast_category="COMMIT",
                expected_close_date=NOW.date() - timedelta(days=1),
            ),
            _row(
                org_id,
                "6.00",
                name="today",
                forecast_category="COMMIT",
                expected_close_date=NOW.date(),
            ),
            _row(
                org_id,
                "7.00",
                name="after",
                forecast_category="COMMIT",
                expected_close_date=date(2026, 6, 1),
            ),
            _row(org_id, "8.00", name="best", forecast_category="BEST_CASE"),
        ]
    )
    db.commit()
    drill = _drill(db, org_id, "COMMIT", periods=3)
    assert [item.name for item in drill.items] == ["today", "in"]
    assert all(item.currency == "INR" for item in drill.items)
    assert drill.currency == "INR"


def test_each_deal_carries_its_own_figures(client: TestClient, db: Session) -> None:
    auth = _auth(client)
    org_id, owner_id = auth["organization"]["id"], auth["user"]["id"]
    db.add_all(
        [
            _row(
                org_id,
                "333.33",
                name="override",
                stage="PROPOSAL",
                probability=33,
                forecast_category="COMMIT",
                owner_user_id=owner_id,
                expected_close_date=date(2026, 4, 30),
            ),
            _row(
                org_id,
                "0.05",
                name="tiny",
                stage="NEGOTIATION",
                forecast_category="COMMIT",
                expected_close_date=date(2026, 3, 20),
            ),
        ]
    )
    db.commit()
    drill = _drill(db, org_id, "COMMIT", periods=3)
    tiny, override = drill.items
    assert tiny.model_dump() == {
        "id": tiny.id,
        "name": "tiny",
        "amount": Decimal("0.05"),
        "currency": "INR",
        "stage": "NEGOTIATION",
        "probability": None,
        "effective_probability": 75,
        "probability_source": "STAGE_DEFAULT",
        "forecast_category": "COMMIT",
        "weighted_amount": Decimal("0.04"),  # 3.75 cents rounds half-up to 4
        "expected_close_date": date(2026, 3, 20),
        "period_start": date(2026, 3, 1),
        "owner_user_id": None,
        "owner_name": None,
    }
    assert override.probability == 33
    assert override.effective_probability == 33
    assert override.probability_source == "OVERRIDE"
    assert override.weighted_amount == Decimal("110.00")  # 109.9989 rounds to 110.00
    assert override.period_start == date(2026, 4, 1)
    assert (override.owner_user_id, override.owner_name) == (owner_id, "Ada Owner")
    assert drill.totals == PipelineWeightedTotals(
        count=2, total_amount=Decimal("333.38"), weighted_amount=Decimal("110.04")
    )


def test_pages_are_stable_and_totals_cover_every_page(client: TestClient, db: Session) -> None:
    _, org_id = _org(client)
    rng = random.Random(11)
    db.add_all(
        [
            _row(
                org_id,
                f"{rng.choice([5, 10, 10, 25])}.00",
                name=f"deal-{index}",
                forecast_category="BEST_CASE",
                expected_close_date=date(2026, 3, 15) + timedelta(days=rng.randint(0, 40)),
            )
            for index in range(23)
        ]
    )
    db.commit()
    everything = _drill(db, org_id, "BEST_CASE", periods=3)
    assert everything.total == 23
    expected_order = sorted(
        everything.items, key=lambda item: (item.expected_close_date, -item.amount, item.id)
    )
    assert everything.items == expected_order

    pages = [_drill(db, org_id, "BEST_CASE", periods=3, limit=5, offset=o) for o in range(0, 25, 5)]
    assert [len(page.items) for page in pages] == [5, 5, 5, 5, 3]
    assert [item for page in pages for item in page.items] == everything.items
    for page in pages:
        assert page.totals == everything.totals
        assert page.total == 23
    past_end = _drill(db, org_id, "BEST_CASE", periods=3, limit=5, offset=50)
    assert past_end.items == []
    assert past_end.totals == everything.totals


def test_api_matches_the_forecast_and_uses_its_defaults(client: TestClient) -> None:
    token, _ = _org(client)
    today = date.today()
    next_month = (today.replace(day=1) + timedelta(days=32)).replace(day=1)
    for amount, category, close in [
        ("100.10", "COMMIT", today),
        ("200.20", "COMMIT", next_month),
        ("300.30", "BEST_CASE", next_month),
        ("400.40", "PIPELINE", today),
        ("500.50", "COMMIT", today - timedelta(days=1)),  # past due
    ]:
        response = _deal(
            client,
            token,
            amount=amount,
            forecast_category=category,
            expected_close_date=close.isoformat(),
        )
        assert response.status_code == 201, response.text

    forecast = _forecast(client, token)
    for category in CATEGORIES:
        response = _get(client, token, category=category)
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["granularity"] == "month"
        assert (body["horizon_start"], body["horizon_end"]) == (
            forecast["horizon_start"],
            forecast["horizon_end"],
        )
        assert (body["range_start"], body["range_end"]) == (
            forecast["horizon_start"],
            forecast["horizon_end"],
        )
        assert (body["limit"], body["offset"]) == (20, 0)
        expected = next(
            row
            for row in forecast["in_horizon_open"]["category_totals"]
            if row["category"] == category
        )
        assert body["totals"] == {k: v for k, v in expected.items() if k != "category"}
        # Money is serialized as exact decimal strings, like every other endpoint.
        assert all(isinstance(item["amount"], str) for item in body["items"])
        assert all(isinstance(item["weighted_amount"], str) for item in body["items"])

        for period in forecast["periods"]:
            by_period = _get(
                client, token, category=category, period_start=period["period_start"]
            ).json()
            expected = next(
                row for row in period["open"]["category_totals"] if row["category"] == category
            )
            assert by_period["totals"] == {k: v for k, v in expected.items() if k != "category"}

    quarter = _get(client, token, category="COMMIT", granularity="quarter").json()
    assert quarter["granularity"] == "quarter"
    assert quarter["horizon_end"] == _forecast(client, token, granularity="quarter")["horizon_end"]
    assert _get(client, token, category="COMMIT", limit=100).status_code == 200


def test_organizations_only_see_their_own_deals(client: TestClient) -> None:
    owner_a = _auth(client, email="a@example.com", organization_name="Org A")["access_token"]
    owner_b = _auth(client, email="b@example.com", organization_name="Org B")["access_token"]
    close = date.today().isoformat()
    for token, amount in ((owner_a, "125000.50"), (owner_b, "1.00")):
        response = _deal(
            client, token, amount=amount, forecast_category="COMMIT", expected_close_date=close
        )
        assert response.status_code == 201, response.text

    a_items = _get(client, owner_a, category="COMMIT").json()
    b_items = _get(client, owner_b, category="COMMIT").json()
    assert [item["amount"] for item in a_items["items"]] == ["125000.50"]
    assert [item["amount"] for item in b_items["items"]] == ["1.00"]
    assert b_items["totals"]["total_amount"] == "1.00"
    assert not {i["id"] for i in a_items["items"]} & {i["id"] for i in b_items["items"]}


def test_every_member_role_can_read_the_drill_down(client: TestClient, db: Session) -> None:
    roles = _org_with_roles(client, db)
    created = _deal(
        client,
        roles["owner"],
        forecast_category="BEST_CASE",
        expected_close_date=date.today().isoformat(),
    )
    assert created.status_code == 201, created.text
    for role in ("owner", "admin", "member"):
        response = _get(client, roles[role], category="BEST_CASE")
        assert response.status_code == 200, response.text
        assert [item["id"] for item in response.json()["items"]] == [created.json()["id"]]


def test_query_count_does_not_grow_with_deals(client: TestClient, db: Session) -> None:
    auth = _auth(client)
    org_id, owner_id = auth["organization"]["id"], auth["user"]["id"]
    statements: list[str] = []

    def count(*args: Any) -> None:
        statements.append(args[2])

    def run(**kwargs: Any) -> int:
        db.expire_all()
        statements.clear()
        engine = db.get_bind()
        event.listen(engine, "before_cursor_execute", count)
        try:
            _drill(db, org_id, "COMMIT", **kwargs)
        finally:
            event.remove(engine, "before_cursor_execute", count)
        return len(statements)

    # Organization, totals, one page with owners joined.
    assert run(periods=3) == 3
    db.add_all(
        [
            _row(
                org_id,
                "1.00",
                forecast_category="COMMIT",
                owner_user_id=owner_id if index % 2 else None,
                expected_close_date=date(2026, 3, 15) + timedelta(days=index % 60),
            )
            for index in range(150)
        ]
    )
    db.commit()
    assert run(periods=3) == 3
    assert run(periods=3, limit=100) == 3
    assert run(periods=24, period_start=date(2026, 4, 1)) == 3


def test_randomized_drill_downs_reconcile_with_the_forecast(
    client: TestClient, db: Session
) -> None:
    _, org_id = _org(client)
    rng = random.Random(2026)
    stages = ["QUALIFICATION", "DISCOVERY", "PROPOSAL", "NEGOTIATION", "CLOSED_WON", "CLOSED_LOST"]
    deals: list[Deal] = []
    for _ in range(250):
        stage = rng.choice(stages)
        closed = stage.startswith("CLOSED")
        deals.append(
            _row(
                org_id,
                f"{rng.randint(0, 99999)}.{rng.randint(0, 99):02d}",
                stage=stage,
                currency=rng.choice(["INR", "INR", "INR", "USD"]),
                probability=None if closed or rng.random() < 0.6 else rng.randint(0, 100),
                forecast_category=rng.choice([None, *CATEGORIES]),
                expected_close_date=date(2025, 10, 1) + timedelta(days=rng.randint(0, 900)),
                closed_at=datetime(2026, 3, 1, tzinfo=UTC) + timedelta(days=rng.randint(0, 60))
                if closed
                else None,
            )
        )
    db.add_all(deals)
    db.commit()

    for granularity, periods in (("month", 1), ("month", 7), ("month", 24), ("quarter", 3)):
        forecast = _run(db, org_id, granularity, periods=periods)
        _assert_drill_down_matches(db, org_id, forecast, granularity, periods)
    for item in _drill(db, org_id, "PIPELINE", periods=24).items:
        deal = db.get(Deal, item.id)
        assert deal is not None
        assert item.effective_probability == effective_probability(deal.stage, deal.probability)

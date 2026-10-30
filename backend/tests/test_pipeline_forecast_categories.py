"""Forecast category totals and Commit / Best Case scenarios: categories regroup the same
per-deal cents as the weighted forecast, and scenarios add full unweighted amounts of
in-horizon open deals to actual won revenue."""

import random
from datetime import UTC, date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import event, text
from sqlalchemy.orm import Session

from app.models.deal import Deal, ForecastCategory, effective_probability
from app.schemas.pipeline import ForecastOpenTotals, PipelineForecast
from app.services.pipeline_service import PipelineService
from tests.test_deals import _deal
from tests.test_leads import _auth
from tests.test_pipeline_forecast import (
    NOW,
    _assert_reconciles,
    _forecast,
    _org,
    _row,
    _run,
    _sum,
)

CATEGORIES = ["PIPELINE", "BEST_CASE", "COMMIT"]
ZERO = Decimal("0.00")


def _by_category(totals: ForecastOpenTotals) -> dict[str, tuple[int, Decimal, Decimal]]:
    return {
        row.category.value: (row.count, row.total_amount, row.weighted_amount)
        for row in totals.category_totals
    }


def _assert_categories_reconcile(forecast: PipelineForecast) -> None:
    """Every bucket's categories add up exactly to the bucket, and in-horizon totals are
    exactly the periods combined (past-due and beyond-horizon deals excluded)."""
    buckets = [
        forecast.past_due,
        *(p.open for p in forecast.periods),
        forecast.beyond_horizon,
        forecast.in_horizon_open,
        forecast.open_pipeline,
    ]
    for bucket in buckets:
        assert [row.category.value for row in bucket.category_totals] == CATEGORIES
        rows = bucket.category_totals
        assert sum(row.count for row in rows) == bucket.count
        assert _sum([row.total_amount for row in rows]) == bucket.total_amount
        assert _sum([row.weighted_amount for row in rows]) == bucket.weighted_amount

    in_horizon = forecast.in_horizon_open
    periods = [p.open for p in forecast.periods]
    assert in_horizon.count == sum(p.count for p in periods)
    assert in_horizon.total_amount == _sum([p.total_amount for p in periods])
    assert in_horizon.weighted_amount == _sum([p.weighted_amount for p in periods])
    assert in_horizon.override_count == sum(p.override_count for p in periods)
    assert forecast.projected_in_horizon_amount == (
        forecast.won_in_horizon.total_amount + in_horizon.weighted_amount
    )
    for index, category in enumerate(CATEGORIES):
        everywhere = [forecast.past_due, *periods, forecast.beyond_horizon]
        overall = forecast.open_pipeline.category_totals[index]
        assert overall.category.value == category
        assert overall.count == sum(b.category_totals[index].count for b in everywhere)
        assert overall.total_amount == _sum(
            [b.category_totals[index].total_amount for b in everywhere]
        )
        assert overall.weighted_amount == _sum(
            [b.category_totals[index].weighted_amount for b in everywhere]
        )
        horizon = in_horizon.category_totals[index]
        assert horizon.total_amount == _sum(
            [p.category_totals[index].total_amount for p in periods]
        )
        assert horizon.weighted_amount == _sum(
            [p.category_totals[index].weighted_amount for p in periods]
        )

    totals = _by_category(in_horizon)
    commit = forecast.won_in_horizon.total_amount + totals["COMMIT"][1]
    assert forecast.commit_scenario_amount == commit
    assert forecast.best_case_scenario_amount == commit + totals["BEST_CASE"][1]


def _store_as_legacy(db: Session) -> None:
    """Deals named "legacy" become open deals written before migration 036: no category
    stored. Raw SQL, because the model's insert default would otherwise set PIPELINE."""
    db.execute(text("UPDATE deals SET forecast_category = NULL WHERE name = 'legacy'"))
    db.commit()


def _seed_mixed(db: Session, org_id: str) -> None:
    db.add_all(
        [
            # March 2026 (current period from NOW = 15 March).
            _row(
                org_id, "100.00", forecast_category="COMMIT", expected_close_date=date(2026, 3, 20)
            ),
            _row(
                org_id,
                "200.00",
                stage="NEGOTIATION",  # 75%
                forecast_category="BEST_CASE",
                expected_close_date=date(2026, 3, 31),
            ),
            _row(
                org_id,
                "400.00",
                forecast_category="PIPELINE",
                expected_close_date=date(2026, 3, 15),
            ),
            # April 2026.
            _row(
                org_id,
                "1000.00",
                stage="PROPOSAL",  # 50%
                forecast_category="COMMIT",
                expected_close_date=date(2026, 4, 1),
            ),
            _row(
                org_id,
                "333.33",
                probability=33,
                forecast_category="COMMIT",
                expected_close_date=date(2026, 4, 30),
            ),
            # Written before migration 036: no category stored, reads as PIPELINE.
            _row(org_id, "50.00", name="legacy", expected_close_date=date(2026, 4, 2)),
            # Past due.
            _row(org_id, "7.00", forecast_category="COMMIT", expected_close_date=date(2026, 3, 14)),
            _row(
                org_id, "9.00", forecast_category="BEST_CASE", expected_close_date=date(2026, 1, 9)
            ),
            # Beyond a 3-month horizon (March to May).
            _row(org_id, "11.00", forecast_category="COMMIT", expected_close_date=date(2026, 6, 1)),
            _row(
                org_id, "13.00", forecast_category="BEST_CASE", expected_close_date=date(2027, 1, 1)
            ),
            # Won in horizon: actual revenue, in both scenarios exactly once. A stale
            # category left by the previous release must not count it as COMMIT too.
            _row(
                org_id,
                "5000.00",
                stage="CLOSED_WON",
                closed_at=datetime(2026, 3, 2, tzinfo=UTC),
                forecast_category="COMMIT",
            ),
            _row(
                org_id, "2500.00", stage="CLOSED_WON", closed_at=datetime(2026, 5, 31, tzinfo=UTC)
            ),
            # Won outside the horizon: not in won_in_horizon, so not in the scenarios.
            _row(
                org_id, "90000.00", stage="CLOSED_WON", closed_at=datetime(2026, 2, 27, tzinfo=UTC)
            ),
            # Lost deals are never forecast, even with a stale COMMIT category.
            _row(org_id, "70000.00", stage="CLOSED_LOST", forecast_category="COMMIT"),
            _row(org_id, "80000.00", stage="CLOSED_LOST", forecast_category="BEST_CASE"),
        ]
    )
    db.commit()
    _store_as_legacy(db)


def test_category_totals_and_scenarios_by_month(client: TestClient, db: Session) -> None:
    _, org_id = _org(client)
    _seed_mixed(db, org_id)
    forecast = _run(db, org_id, periods=3)

    march, april, may = forecast.periods
    assert _by_category(march.open) == {
        "PIPELINE": (1, Decimal("400.00"), Decimal("40.00")),
        "BEST_CASE": (1, Decimal("200.00"), Decimal("150.00")),
        "COMMIT": (1, Decimal("100.00"), Decimal("10.00")),
    }
    assert _by_category(april.open) == {
        "PIPELINE": (1, Decimal("50.00"), Decimal("5.00")),
        "BEST_CASE": (0, ZERO, ZERO),
        # 1000.00 * 50% = 500.00; 333.33 * 33% = 109.9989 -> 110.00 (per deal).
        "COMMIT": (2, Decimal("1333.33"), Decimal("610.00")),
    }
    assert _by_category(may.open) == {category: (0, ZERO, ZERO) for category in CATEGORIES}
    assert _by_category(forecast.past_due) == {
        "PIPELINE": (0, ZERO, ZERO),
        "BEST_CASE": (1, Decimal("9.00"), Decimal("0.90")),
        "COMMIT": (1, Decimal("7.00"), Decimal("0.70")),
    }
    assert _by_category(forecast.beyond_horizon) == {
        "PIPELINE": (0, ZERO, ZERO),
        "BEST_CASE": (1, Decimal("13.00"), Decimal("1.30")),
        "COMMIT": (1, Decimal("11.00"), Decimal("1.10")),
    }
    assert _by_category(forecast.in_horizon_open) == {
        "PIPELINE": (2, Decimal("450.00"), Decimal("45.00")),
        "BEST_CASE": (1, Decimal("200.00"), Decimal("150.00")),
        "COMMIT": (3, Decimal("1433.33"), Decimal("620.00")),
    }
    assert _by_category(forecast.open_pipeline) == {
        "PIPELINE": (2, Decimal("450.00"), Decimal("45.00")),
        "BEST_CASE": (3, Decimal("222.00"), Decimal("152.20")),
        "COMMIT": (5, Decimal("1451.33"), Decimal("621.80")),
    }

    assert forecast.won_in_horizon.total_amount == Decimal("7500.00")
    # Commit: won 7500.00 + full COMMIT 1433.33. Past-due and beyond-horizon deals are
    # outside the horizon; weighted amounts are never used.
    assert forecast.commit_scenario_amount == Decimal("8933.33")
    # Best case is cumulative: commit + full BEST_CASE 200.00. PIPELINE is in neither.
    assert forecast.best_case_scenario_amount == Decimal("9133.33")
    # The weighted forecast is untouched: won + 45.00 + 150.00 + 620.00.
    assert forecast.projected_in_horizon_amount == Decimal("8315.00")
    _assert_reconciles(forecast)
    _assert_categories_reconcile(forecast)


def test_category_totals_and_scenarios_by_quarter(client: TestClient, db: Session) -> None:
    _, org_id = _org(client)
    _seed_mixed(db, org_id)
    forecast = _run(db, org_id, "quarter", periods=2)

    q1, q2 = forecast.periods
    assert (q1.label, q2.label) == ("2026-Q1", "2026-Q2")
    assert _by_category(q1.open)["COMMIT"] == (1, Decimal("100.00"), Decimal("10.00"))
    # Q2 now holds April and the 1 June COMMIT deal that was beyond a 3-month horizon.
    assert _by_category(q2.open)["COMMIT"] == (3, Decimal("1344.33"), Decimal("611.10"))
    assert _by_category(forecast.beyond_horizon) == {
        "PIPELINE": (0, ZERO, ZERO),
        "BEST_CASE": (1, Decimal("13.00"), Decimal("1.30")),
        "COMMIT": (0, ZERO, ZERO),
    }
    # Q1 includes the 27 February win: 90000.00 + 5000.00 + 2500.00 in Q2.
    assert forecast.won_in_horizon.total_amount == Decimal("97500.00")
    assert forecast.commit_scenario_amount == Decimal("98944.33")
    assert forecast.best_case_scenario_amount == Decimal("99144.33")
    _assert_reconciles(forecast)
    _assert_categories_reconcile(forecast)


def test_scenarios_are_cumulative_and_ignore_pipeline_deals(
    client: TestClient, db: Session
) -> None:
    _, org_id = _org(client)
    close = date(2026, 4, 10)
    db.add_all(
        [
            _row(org_id, "10.00", forecast_category="PIPELINE", expected_close_date=close),
            _row(org_id, "999.99", forecast_category="PIPELINE", stage="NEGOTIATION"),
        ]
    )
    db.commit()
    only_pipeline = _run(db, org_id)
    # No won revenue, no COMMIT and no BEST_CASE: both scenarios are zero although the
    # weighted forecast is not.
    assert only_pipeline.commit_scenario_amount == ZERO
    assert only_pipeline.best_case_scenario_amount == ZERO
    assert only_pipeline.projected_in_horizon_amount == Decimal("750.99")

    db.add(_row(org_id, "300.00", forecast_category="BEST_CASE", expected_close_date=close))
    db.commit()
    with_best_case = _run(db, org_id)
    assert with_best_case.commit_scenario_amount == ZERO
    assert with_best_case.best_case_scenario_amount == Decimal("300.00")

    db.add(_row(org_id, "45.67", forecast_category="COMMIT", expected_close_date=close))
    db.commit()
    with_commit = _run(db, org_id)
    assert with_commit.commit_scenario_amount == Decimal("45.67")
    # Best case already contains commit; the two are never added together.
    assert with_commit.best_case_scenario_amount == Decimal("345.67")
    assert with_commit.best_case_scenario_amount >= with_commit.commit_scenario_amount
    _assert_categories_reconcile(with_commit)


def test_won_only_scenarios_equal_actual_revenue(client: TestClient, db: Session) -> None:
    _, org_id = _org(client)
    db.add_all(
        [
            _row(org_id, "1234.56", stage="CLOSED_WON", closed_at=datetime(2026, 3, 1, tzinfo=UTC)),
            _row(org_id, "500.00", stage="CLOSED_LOST", forecast_category="COMMIT"),
        ]
    )
    db.commit()
    forecast = _run(db, org_id)
    assert forecast.open_pipeline.count == 0
    assert forecast.commit_scenario_amount == Decimal("1234.56")
    assert forecast.best_case_scenario_amount == Decimal("1234.56")
    assert all(row.count == 0 for row in forecast.open_pipeline.category_totals)
    _assert_categories_reconcile(forecast)


def test_other_currencies_are_excluded_from_categories_and_scenarios(
    client: TestClient, db: Session
) -> None:
    _, org_id = _org(client)
    db.add_all(
        [
            _row(org_id, "100.00", forecast_category="COMMIT"),
            _row(org_id, "5000.00", currency="USD", forecast_category="COMMIT"),
            _row(org_id, "6000.00", currency="USD", forecast_category="BEST_CASE"),
            _row(org_id, "7000.00", currency="USD", stage="CLOSED_WON"),
            _row(org_id, "8000.00", currency="EUR", forecast_category="PIPELINE"),
        ]
    )
    db.commit()
    forecast = _run(db, org_id)
    assert forecast.excluded_other_currency_count == 4
    assert _by_category(forecast.open_pipeline) == {
        "PIPELINE": (0, ZERO, ZERO),
        "BEST_CASE": (0, ZERO, ZERO),
        "COMMIT": (1, Decimal("100.00"), Decimal("10.00")),
    }
    assert forecast.commit_scenario_amount == Decimal("100.00")
    assert forecast.best_case_scenario_amount == Decimal("100.00")
    _assert_categories_reconcile(forecast)


def test_api_returns_category_totals_as_decimal_strings(client: TestClient) -> None:
    token, _ = _org(client)
    close = (date.today().replace(day=1) + timedelta(days=40)).isoformat()
    _deal(client, token, amount="999999999999.99", stage="NEGOTIATION", expected_close_date=close)
    _deal(
        client,
        token,
        amount="333.33",
        probability=33,
        forecast_category="COMMIT",
        expected_close_date=close,
    )
    _deal(client, token, amount="0.05", forecast_category="BEST_CASE", expected_close_date=close)

    forecast = _forecast(client, token, granularity="month", periods=3)
    period = forecast["periods"][1]
    assert period["open"]["category_totals"] == [
        {
            "count": 1,
            "total_amount": "999999999999.99",
            "weighted_amount": "749999999999.99",
            "category": "PIPELINE",
        },
        {"count": 1, "total_amount": "0.05", "weighted_amount": "0.01", "category": "BEST_CASE"},
        {"count": 1, "total_amount": "333.33", "weighted_amount": "110.00", "category": "COMMIT"},
    ]
    assert forecast["in_horizon_open"]["category_totals"] == period["open"]["category_totals"]
    assert forecast["in_horizon_open"]["weighted_amount"] == "750000000110.00"
    assert forecast["commit_scenario_amount"] == "333.33"
    assert forecast["best_case_scenario_amount"] == "333.38"
    assert forecast["past_due"]["category_totals"][2] == {
        "count": 0,
        "total_amount": "0.00",
        "weighted_amount": "0.00",
        "category": "COMMIT",
    }

    quarters = _forecast(client, token, granularity="quarter", periods=2)
    assert quarters["commit_scenario_amount"] == "333.33"
    assert quarters["best_case_scenario_amount"] == "333.38"


def test_categories_and_scenarios_are_isolated_between_organizations(client: TestClient) -> None:
    token, _ = _org(client)
    close = (date.today().replace(day=1) + timedelta(days=40)).isoformat()
    _deal(client, token, amount="400.00", forecast_category="COMMIT", expected_close_date=close)

    other = _auth(client, email="other@example.com", organization_name="Org B")
    isolated = _forecast(client, other["access_token"])
    assert isolated["commit_scenario_amount"] == "0.00"
    assert isolated["best_case_scenario_amount"] == "0.00"
    assert all(row["count"] == 0 for row in isolated["open_pipeline"]["category_totals"])
    assert _forecast(client, token)["commit_scenario_amount"] == "400.00"


def test_randomized_categories_match_a_per_deal_decimal_reference(
    client: TestClient, db: Session
) -> None:
    _, org_id = _org(client)
    rng = random.Random(4_2026)
    stages = ["QUALIFICATION", "DISCOVERY", "PROPOSAL", "NEGOTIATION"]
    open_rows: list[Deal] = []
    won_rows: list[Deal] = []
    for _ in range(400):
        amount = f"{rng.randint(0, 10**9)}.{rng.randint(0, 99):02d}"
        if rng.random() < 0.15:
            won_rows.append(
                _row(
                    org_id,
                    amount,
                    stage="CLOSED_WON",
                    closed_at=datetime(2026, 1, 1, tzinfo=UTC)
                    + timedelta(hours=rng.randint(0, 24 * 400)),
                )
            )
            continue
        stored = rng.choice([None, *CATEGORIES])
        open_rows.append(
            _row(
                org_id,
                amount,
                name="legacy" if stored is None else "Deal",
                stage=rng.choice(stages),
                probability=rng.choice([None, None, rng.randint(0, 100)]),
                forecast_category=stored,
                currency=rng.choice(["INR", "INR", "INR", "USD"]),
                expected_close_date=date(2026, 1, 1) + timedelta(days=rng.randint(0, 500)),
            )
        )
    db.add_all([*open_rows, *won_rows])
    db.commit()
    _store_as_legacy(db)
    assert db.scalar(text("SELECT count(*) FROM deals WHERE forecast_category IS NULL"))

    def weighted(deal: Deal) -> Decimal:
        value = deal.amount * effective_probability(deal.stage, deal.probability) / 100
        return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    def category(deal: Deal) -> str:
        if deal.name == "legacy":
            return ForecastCategory.PIPELINE.value
        return str(deal.forecast_category)

    for granularity, periods in (("month", 12), ("quarter", 3)):
        forecast = _run(db, org_id, granularity, periods=periods)
        _assert_reconciles(forecast)
        _assert_categories_reconcile(forecast)
        start = forecast.horizon_start
        end = forecast.horizon_end
        inr = [d for d in open_rows if d.currency == "INR"]
        in_horizon = [d for d in inr if max(start, NOW.date()) <= d.expected_close_date <= end]
        past_due = [d for d in inr if d.expected_close_date < NOW.date()]
        beyond = [d for d in inr if d.expected_close_date > end]
        won = _sum(
            [
                d.amount
                for d in won_rows
                if d.closed_at is not None and start <= d.closed_at.date() <= end
            ]
        )
        for bucket, deals in (
            (forecast.in_horizon_open, in_horizon),
            (forecast.past_due, past_due),
            (forecast.beyond_horizon, beyond),
            (forecast.open_pipeline, inr),
        ):
            for row in bucket.category_totals:
                members = [d for d in deals if category(d) == row.category.value]
                assert row.count == len(members)
                assert row.total_amount == _sum([d.amount for d in members])
                assert row.weighted_amount == _sum([weighted(d) for d in members])

        commit = _sum([d.amount for d in in_horizon if category(d) == "COMMIT"])
        best = _sum([d.amount for d in in_horizon if category(d) == "BEST_CASE"])
        assert forecast.won_in_horizon.total_amount == won
        assert forecast.commit_scenario_amount == won + commit
        assert forecast.best_case_scenario_amount == won + commit + best


def test_category_aggregation_adds_no_queries(client: TestClient, db: Session) -> None:
    _, org_id = _org(client)
    statements: list[str] = []

    def count(*args: Any) -> None:
        statements.append(args[2])

    def run(granularity: str, periods: int) -> int:
        db.expire_all()
        statements.clear()
        engine = db.get_bind()
        event.listen(engine, "before_cursor_execute", count)
        try:
            _run(db, org_id, granularity, periods=periods)
        finally:
            event.remove(engine, "before_cursor_execute", count)
        return len(statements)

    db.add(_row(org_id, "1.00", forecast_category="COMMIT"))
    db.commit()
    # Organization, open deals (one grouped query), won deals, other-currency count.
    assert run("month", 1) == 4
    rng = random.Random(7)
    db.add_all(
        [
            _row(
                org_id,
                "1.00",
                forecast_category=rng.choice([None, *CATEGORIES]),
                expected_close_date=date(2026, 1, 1) + timedelta(days=rng.randint(0, 900)),
            )
            for _ in range(120)
        ]
    )
    db.commit()
    assert run("month", 24) == 4
    assert run("quarter", 8) == 4
    assert sum("deals" in statement for statement in statements) == 3


def test_all_horizon_categories_reconcile_with_the_pipeline_summary(
    client: TestClient, db: Session
) -> None:
    _, org_id = _org(client)
    _seed_mixed(db, org_id)
    forecast = _run(db, org_id, periods=24)
    summary = PipelineService(db).summary(org_id, months=1, now=NOW)
    # All-horizon categories add up to the same open totals the summary reports.
    assert _sum([r.total_amount for r in forecast.open_pipeline.category_totals]) == (
        summary.open.total_amount
    )
    assert _sum([r.weighted_amount for r in forecast.open_pipeline.category_totals]) == (
        summary.open.weighted_amount
    )

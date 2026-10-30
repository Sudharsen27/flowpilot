"""Forecast vs sales targets: organization-wide monthly targets summed per period and over
the horizon, compared with won revenue, the Commit / Best Case scenarios and the
projected figure. Comparisons appear only when every month in the range has a target;
owner targets are never added in."""

import random
from datetime import UTC, date, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.orm import Session

from app.models.sales_target import SalesTarget
from app.schemas.pipeline import ForecastTarget, PipelineForecast
from app.schemas.sales_targets import month_end
from app.services.pipeline_service import _attainment_percent
from tests.test_deals import _org_with_roles
from tests.test_leads import _auth
from tests.test_pipeline_forecast import _forecast, _row, _run, _sum
from tests.test_pipeline_forecast_categories import CATEGORIES, _seed_mixed

BASES = ["WON", "COMMIT_SCENARIO", "BEST_CASE_SCENARIO", "PROJECTED"]
TARGET_FIELDS = {"target", "commit_scenario_amount", "best_case_scenario_amount"}


def _org(client: TestClient, email: str = "owner@example.com") -> tuple[str, str, str]:
    auth = _auth(client, email=email, organization_name=email)
    return auth["access_token"], auth["organization"]["id"], auth["user"]["id"]


def _target(
    org_id: str, month: date, amount: str, owner_user_id: str | None = None, currency: str = "INR"
) -> SalesTarget:
    return SalesTarget(
        organization_id=org_id,
        owner_user_id=owner_user_id,
        period_start=month,
        period_end=month_end(month),
        amount=Decimal(amount),
        currency=currency,
    )


def _comparisons(target: ForecastTarget) -> dict[str, tuple[Decimal, str | None, Decimal, Decimal]]:
    assert [c.basis.value for c in target.comparisons] == BASES
    return {
        c.basis.value: (c.amount, c.attainment_percent, c.remaining_amount, c.above_target_amount)
        for c in target.comparisons
    }


def _d(value: str) -> Decimal:
    return Decimal(value)


def _without_targets(forecast: PipelineForecast) -> dict[str, Any]:
    """Every field that existed before targets, assumptions aside."""
    dumped = forecast.model_dump(exclude={"target_in_horizon", "assumptions"})
    for period in dumped["periods"]:
        for field in TARGET_FIELDS:
            del period[field]
    return dumped


def test_full_monthly_target_compares_all_four_figures(client: TestClient, db: Session) -> None:
    _, org_id, _ = _org(client)
    db.add_all(
        [
            _row(org_id, "300.00", stage="CLOSED_WON"),  # closed at NOW, March
            # 10% each: weighted 20 + 10 + 40 = 70.
            _row(
                org_id, "200.00", forecast_category="COMMIT", expected_close_date=date(2026, 3, 20)
            ),
            _row(
                org_id,
                "100.00",
                forecast_category="BEST_CASE",
                expected_close_date=date(2026, 3, 25),
            ),
            _row(
                org_id,
                "400.00",
                forecast_category="PIPELINE",
                expected_close_date=date(2026, 3, 31),
            ),
            _target(org_id, date(2026, 3, 1), "1000.00"),
        ]
    )
    db.commit()

    forecast = _run(db, org_id, periods=1)
    period = forecast.periods[0]
    assert period.commit_scenario_amount == _d("500.00")
    assert period.best_case_scenario_amount == _d("600.00")
    target = period.target
    assert target.status == "FULL"
    assert target.amount == _d("1000.00")
    assert (target.months_in_range, target.months_with_target) == (1, 1)
    assert target.missing_months == []
    assert target.has_owner_targets is False
    assert _comparisons(target) == {
        "WON": (_d("300.00"), "30.0", _d("700.00"), _d("0.00")),
        "COMMIT_SCENARIO": (_d("500.00"), "50.0", _d("500.00"), _d("0.00")),
        "BEST_CASE_SCENARIO": (_d("600.00"), "60.0", _d("400.00"), _d("0.00")),
        "PROJECTED": (_d("370.00"), "37.0", _d("630.00"), _d("0.00")),
    }
    # One period: the horizon is the same month.
    assert forecast.target_in_horizon == target
    assert "TARGETS_INCOMPLETE" not in [a.code for a in forecast.assumptions]


def test_quarter_targets_sum_their_months_and_report_partial_and_missing(
    client: TestClient, db: Session
) -> None:
    _, org_id, _ = _org(client)
    db.add_all(
        [
            # Q1 2026 fully set, including months before as_of (15 March).
            _target(org_id, date(2026, 1, 1), "100.00"),
            _target(org_id, date(2026, 2, 1), "200.00"),
            _target(org_id, date(2026, 3, 1), "300.01"),
            # Q2 2026: two of three months.
            _target(org_id, date(2026, 4, 1), "50.00"),
            _target(org_id, date(2026, 5, 1), "60.00"),
            # Q3 2026: none.
            _row(org_id, "1000.00", stage="CLOSED_WON"),
            _row(org_id, "90.00", forecast_category="COMMIT", expected_close_date=date(2026, 5, 2)),
        ]
    )
    db.commit()

    forecast = _run(db, org_id, "quarter", periods=3)
    q1, q2, q3 = (period.target for period in forecast.periods)

    assert q1.status == "FULL"
    assert q1.amount == _d("600.01")
    assert (q1.months_in_range, q1.months_with_target, q1.missing_months) == (3, 3, [])
    assert _comparisons(q1)["WON"] == (_d("1000.00"), "166.7", _d("0.00"), _d("399.99"))

    assert q2.status == "PARTIAL"
    assert q2.amount == _d("110.00")
    assert (q2.months_in_range, q2.months_with_target) == (3, 2)
    assert q2.missing_months == [date(2026, 6, 1)]
    assert q2.comparisons == []

    assert q3.status == "NONE"
    assert q3.amount is None
    assert (q3.months_in_range, q3.months_with_target) == (3, 0)
    assert q3.missing_months == [date(2026, 7, 1), date(2026, 8, 1), date(2026, 9, 1)]
    assert q3.comparisons == []

    horizon = forecast.target_in_horizon
    assert horizon.status == "PARTIAL"
    assert horizon.amount == _d("710.01")
    assert (horizon.months_in_range, horizon.months_with_target) == (9, 5)
    assert horizon.missing_months == [date(2026, m, 1) for m in (6, 7, 8, 9)]
    assert horizon.comparisons == []
    incomplete = [a for a in forecast.assumptions if a.code == "TARGETS_INCOMPLETE"]
    assert len(incomplete) == 1
    assert incomplete[0].detail.startswith("4 of 9 month(s)")


def test_owner_targets_are_flagged_but_never_added(client: TestClient, db: Session) -> None:
    _, org_id, owner_id = _org(client)
    db.add_all(
        [
            _target(org_id, date(2026, 3, 1), "500.00"),
            _target(org_id, date(2026, 3, 1), "900.00", owner_user_id=owner_id),
            # April has only an owner target.
            _target(org_id, date(2026, 4, 1), "700.00", owner_user_id=owner_id),
        ]
    )
    db.commit()

    forecast = _run(db, org_id, periods=3)
    march, april, may = (period.target for period in forecast.periods)
    assert (march.status, march.amount, march.has_owner_targets) == ("FULL", _d("500.00"), True)
    assert (april.status, april.amount, april.has_owner_targets) == ("NONE", None, True)
    assert (may.status, may.amount, may.has_owner_targets) == ("NONE", None, False)
    horizon = forecast.target_in_horizon
    assert (horizon.status, horizon.amount, horizon.has_owner_targets) == (
        "PARTIAL",
        _d("500.00"),
        True,
    )


def test_targets_outside_the_horizon_other_currencies_and_organizations_are_ignored(
    client: TestClient, db: Session
) -> None:
    _, org_id, _ = _org(client)
    _, other_id, _ = _org(client, email="other@example.com")
    db.add_all(
        [
            _target(org_id, date(2026, 2, 1), "1.00"),  # before the horizon
            _target(org_id, date(2026, 3, 1), "10.00"),
            _target(org_id, date(2026, 4, 1), "20.00", currency="USD"),  # not converted
            _target(org_id, date(2026, 6, 1), "1.00"),  # after a March-May horizon
            _target(other_id, date(2026, 3, 1), "99999.00"),
            _target(other_id, date(2026, 5, 1), "99999.00"),
        ]
    )
    db.commit()

    forecast = _run(db, org_id, periods=3)
    statuses = [(p.target.status, p.target.amount) for p in forecast.periods]
    assert statuses == [("FULL", _d("10.00")), ("NONE", None), ("NONE", None)]
    assert forecast.target_in_horizon.amount == _d("10.00")
    assert forecast.target_in_horizon.months_with_target == 1


def test_zero_target_has_no_percentage_and_equal_figures_have_no_gap(
    client: TestClient, db: Session
) -> None:
    _, org_id, _ = _org(client)
    db.add_all(
        [
            _row(org_id, "100.00", stage="CLOSED_WON"),
            _target(org_id, date(2026, 3, 1), "0.00"),
            _target(org_id, date(2026, 4, 1), "250.00"),
            _row(
                org_id,
                "250.00",
                stage="CLOSED_WON",
                closed_at=datetime(2026, 4, 3, tzinfo=UTC),
            ),
        ]
    )
    db.commit()

    forecast = _run(db, org_id, periods=2)
    march, april = (period.target for period in forecast.periods)
    assert (march.status, march.amount) == ("FULL", _d("0.00"))
    assert _comparisons(march)["WON"] == (_d("100.00"), None, _d("0.00"), _d("100.00"))
    assert _comparisons(march)["COMMIT_SCENARIO"][1] is None
    assert _comparisons(april)["WON"] == (_d("250.00"), "100.0", _d("0.00"), _d("0.00"))


@pytest.mark.parametrize(
    ("cents", "target", "expected"),
    [
        (0, 100, "0.0"),
        (1, 3, "33.3"),
        (2, 3, "66.7"),
        (1, 8, "12.5"),
        # Exactly half a tenth rounds up: 0.05% and 0.15%.
        (1, 2000, "0.1"),
        (3, 2000, "0.2"),
        # Just under half rounds down: 0.0499...%.
        (499, 1_000_000, "0.0"),
        (250, 100, "250.0"),
        (99_999_999_999_999, 1, "9999999999999900.0"),
        (5, 0, None),
        (0, 0, None),
    ],
)
def test_attainment_percent_rounds_half_up_to_one_decimal(
    cents: int, target: int, expected: str | None
) -> None:
    assert _attainment_percent(cents, target) == expected


def test_per_period_scenarios_reconcile_with_the_horizon(client: TestClient, db: Session) -> None:
    _, org_id, _ = _org(client)
    _seed_mixed(db, org_id)
    for granularity, periods in (("month", 3), ("quarter", 2)):
        forecast = _run(db, org_id, granularity, periods=periods)
        for period in forecast.periods:
            categories = {
                row.category.value: row.total_amount for row in period.open.category_totals
            }
            commit = period.won.total_amount + categories["COMMIT"]
            assert period.commit_scenario_amount == commit
            assert period.best_case_scenario_amount == commit + categories["BEST_CASE"]
        assert _sum([p.commit_scenario_amount for p in forecast.periods]) == (
            forecast.commit_scenario_amount
        )
        assert _sum([p.best_case_scenario_amount for p in forecast.periods]) == (
            forecast.best_case_scenario_amount
        )


def test_targets_do_not_change_any_existing_forecast_field(client: TestClient, db: Session) -> None:
    _, org_id, owner_id = _org(client)
    _seed_mixed(db, org_id)
    before = {g: _run(db, org_id, g, periods=3) for g in ("month", "quarter")}
    db.add_all(
        [_target(org_id, date(2026, month, 1), f"{month}000.00") for month in range(1, 13)]
        + [_target(org_id, date(2026, 3, 1), "5.00", owner_user_id=owner_id)]
    )
    db.commit()
    for granularity, earlier in before.items():
        later = _run(db, org_id, granularity, periods=3)
        assert _without_targets(later) == _without_targets(earlier)
        assert later.target_in_horizon.status == "FULL"
        assert earlier.target_in_horizon.status == "NONE"
        codes = [a.code for a in later.assumptions]
        assert codes == [a.code for a in earlier.assumptions if a.code != "TARGETS_INCOMPLETE"]


def test_randomized_targets_match_a_decimal_reference(client: TestClient, db: Session) -> None:
    _, org_id, owner_id = _org(client)
    rng = random.Random(4_2027)
    _seed_mixed(db, org_id)
    targets: dict[date, Decimal] = {}
    month = date(2025, 12, 1)
    for _ in range(30):
        if rng.random() < 0.7:
            amount = Decimal(f"{rng.randint(0, 10**9)}.{rng.randint(0, 99):02d}")
            targets[month] = amount
            db.add(_target(org_id, month, str(amount)))
        if rng.random() < 0.3:
            db.add(_target(org_id, month, "123.45", owner_user_id=owner_id))
        month = date(month.year + month.month // 12, month.month % 12 + 1, 1)
    db.commit()

    def reference(target: ForecastTarget, months: list[date]) -> None:
        present = [m for m in months if m in targets]
        assert target.missing_months == [m for m in months if m not in targets]
        assert target.months_with_target == len(present)
        expected_status = (
            "NONE" if not present else "FULL" if len(present) == len(months) else "PARTIAL"
        )
        assert target.status == expected_status
        if not present:
            assert target.amount is None
            return
        amount = _sum([targets[m] for m in present])
        assert target.amount == amount
        if expected_status != "FULL":
            assert target.comparisons == []
            return
        for comparison in target.comparisons:
            figure = comparison.amount
            if amount == 0:
                assert comparison.attainment_percent is None
            else:
                percent = (figure / amount * 100).quantize(Decimal("0.1"), ROUND_HALF_UP)
                assert comparison.attainment_percent == str(percent)
            assert comparison.remaining_amount == max(amount - figure, Decimal("0.00"))
            assert comparison.above_target_amount == max(figure - amount, Decimal("0.00"))

    for granularity, step, periods in (("month", 1, 24), ("quarter", 3, 8)):
        forecast = _run(db, org_id, granularity, periods=periods)
        all_months: list[date] = []
        for period in forecast.periods:
            start = period.period_start
            months = [
                date(start.year + (start.month - 1 + i) // 12, (start.month - 1 + i) % 12 + 1, 1)
                for i in range(step)
            ]
            all_months += months
            reference(period.target, months)
            figures = {c.basis.value: c.amount for c in period.target.comparisons}
            if figures:
                assert figures == {
                    "WON": period.won.total_amount,
                    "COMMIT_SCENARIO": period.commit_scenario_amount,
                    "BEST_CASE_SCENARIO": period.best_case_scenario_amount,
                    "PROJECTED": period.projected_amount,
                }
        reference(forecast.target_in_horizon, all_months)


def test_api_returns_targets_as_strings_for_every_role(client: TestClient, db: Session) -> None:
    roles = _org_with_roles(client, db)
    db.add_all(
        [
            _target(roles["org_id"], date.today().replace(day=1), "1234.5"),
            _row(roles["org_id"], "100.00", stage="CLOSED_WON", closed_at=datetime.now(UTC)),
        ]
    )
    db.commit()
    for role in ("owner", "admin", "member"):
        forecast = _forecast(client, roles[role], periods=1)
        target = forecast["periods"][0]["target"]
        assert target["status"] == "FULL"
        assert target["amount"] == "1234.50"
        assert target["has_owner_targets"] is False
        assert target["comparisons"][0] == {
            "basis": "WON",
            "amount": "100.00",
            "attainment_percent": "8.1",
            "remaining_amount": "1134.50",
            "above_target_amount": "0.00",
        }
        assert forecast["periods"][0]["commit_scenario_amount"] == "100.00"
        assert forecast["target_in_horizon"] == target

    empty = _forecast(client, roles["owner"], periods=2)
    assert empty["periods"][1]["target"] == {
        "status": "NONE",
        "amount": None,
        "months_in_range": 1,
        "months_with_target": 0,
        "missing_months": [empty["periods"][1]["period_start"]],
        "has_owner_targets": False,
        "comparisons": [],
    }

    other = _auth(client, email="else@example.com", organization_name="Else")
    isolated = _forecast(client, other["access_token"], periods=1)
    assert isolated["target_in_horizon"]["status"] == "NONE"


def test_targets_add_one_query_whatever_their_number(client: TestClient, db: Session) -> None:
    _, org_id, owner_id = _org(client)
    statements: list[str] = []

    def count(*args: Any) -> None:
        statements.append(args[2])

    def run() -> int:
        db.expire_all()
        statements.clear()
        engine = db.get_bind()
        event.listen(engine, "before_cursor_execute", count)
        try:
            _run(db, org_id, "quarter", periods=8)
        finally:
            event.remove(engine, "before_cursor_execute", count)
        return len(statements)

    db.add(_row(org_id, "1.00", forecast_category=CATEGORIES[0]))
    db.commit()
    without = run()
    month = date(2026, 1, 1)
    for _ in range(24):
        db.add_all(
            [
                _target(org_id, month, "1.00"),
                _target(org_id, month, "1.00", owner_user_id=owner_id),
            ]
        )
        month = date(month.year + month.month // 12, month.month % 12 + 1, 1)
    db.commit()
    assert run() == without == 5
    assert sum("sales_targets" in statement for statement in statements) == 1


def test_forecast_with_targets_is_read_only(client: TestClient, db: Session) -> None:
    _, org_id, _ = _org(client)
    db.add(_target(org_id, date(2026, 3, 1), "10.00"))
    db.commit()
    updated_at = db.query(SalesTarget).one().updated_at
    _run(db, org_id)
    db.expire_all()
    again = db.query(SalesTarget).one()
    assert (again.amount, again.updated_at) == (Decimal("10.00"), updated_at)

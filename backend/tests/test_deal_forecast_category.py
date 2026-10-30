"""Forecast categories: stored on open deals, independent of stage and probability,
cleared when a deal closes, recorded in history, and invisible to the forecast maths."""

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.deal import Deal, DealStageEvent
from app.models.organization import Organization
from tests.test_agent_runtime import _headers
from tests.test_deals import _deal, _history, _org_with_roles, _stage
from tests.test_leads import _auth


def _patch(client: TestClient, token: str, deal: dict[str, Any], **body: Any) -> Any:
    return client.patch(
        f"/api/v1/deals/{deal['id']}",
        json={"expected_revision": deal["revision"], **body},
        headers=_headers(token),
    )


def _list(client: TestClient, token: str, **params: str) -> Any:
    return client.get("/api/v1/deals", params=params, headers=_headers(token))


def test_new_open_deals_default_to_pipeline(client: TestClient, db: Session) -> None:
    roles = _org_with_roles(client, db)
    for role in ("owner", "admin", "member"):
        created = _deal(client, roles[role])
        assert created.status_code == 201, created.text
        deal = created.json()
        assert deal["forecast_category"] == "PIPELINE"
        [event] = _history(client, roles["owner"], deal["id"])
        assert event["changes"] == ["CREATED"]
        assert (event["previous_forecast_category"], event["new_forecast_category"]) == (
            None,
            "PIPELINE",
        )


def test_open_deals_can_be_created_in_any_category(client: TestClient, db: Session) -> None:
    roles = _org_with_roles(client, db)
    for category in ("PIPELINE", "BEST_CASE", "COMMIT"):
        deal = _deal(client, roles["member"], forecast_category=category, stage="DISCOVERY")
        assert deal.status_code == 201, deal.text
        assert deal.json()["forecast_category"] == category


@pytest.mark.parametrize("stage", ["CLOSED_WON", "CLOSED_LOST"])
def test_closed_deals_have_no_category(client: TestClient, db: Session, stage: str) -> None:
    roles = _org_with_roles(client, db)
    extra = {"lost_reason": "No budget"} if stage == "CLOSED_LOST" else {}
    created = _deal(client, roles["owner"], stage=stage, **extra)
    assert created.status_code == 201, created.text
    assert created.json()["forecast_category"] is None
    [event] = _history(client, roles["owner"], created.json()["id"])
    assert event["new_forecast_category"] is None

    rejected = _deal(client, roles["owner"], stage=stage, forecast_category="COMMIT", **extra)
    assert rejected.status_code == 422
    assert "no forecast category" in rejected.json()["detail"]


@pytest.mark.parametrize("value", ["CLOSED", "OMITTED", "commit", "", 3])
def test_unknown_categories_are_rejected(client: TestClient, db: Session, value: Any) -> None:
    roles = _org_with_roles(client, db)
    assert _deal(client, roles["owner"], forecast_category=value).status_code == 422
    deal = _deal(client, roles["owner"]).json()
    assert _patch(client, roles["owner"], deal, forecast_category=value).status_code == 422
    assert _list(client, roles["owner"], forecast_category=str(value)).status_code == 422


@pytest.mark.parametrize("role", ["owner", "admin", "member"])
def test_every_role_changes_an_open_deals_category_with_history(
    client: TestClient, db: Session, role: str
) -> None:
    roles = _org_with_roles(client, db)
    # A deal owned by someone else: open-deal edits are not limited to the deal owner.
    deal = _deal(client, roles["owner"], stage="PROPOSAL", probability=55).json()
    response = _patch(
        client, roles[role], deal, forecast_category="COMMIT", change_reason="Verbal yes"
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["forecast_category"] == "COMMIT"
    assert body["revision"] == deal["revision"] + 1
    # Category is independent of stage and probability.
    assert (body["stage"], body["probability"], body["effective_probability"]) == (
        "PROPOSAL",
        55,
        55,
    )

    event = _history(client, roles["owner"], deal["id"])[-1]
    assert event["changes"] == ["FORECAST_CATEGORY"]
    assert (event["previous_forecast_category"], event["new_forecast_category"]) == (
        "PIPELINE",
        "COMMIT",
    )
    assert event["changed_by_user_id"] == roles[f"{role}_id"]
    assert event["change_reason"] == "Verbal yes"


def test_unchanged_category_is_a_no_op(client: TestClient, db: Session) -> None:
    roles = _org_with_roles(client, db)
    deal = _deal(client, roles["member"]).json()
    response = _patch(client, roles["member"], deal, forecast_category="PIPELINE")
    assert response.status_code == 200
    assert response.json()["revision"] == deal["revision"]
    assert len(_history(client, roles["member"], deal["id"])) == 1


def test_category_and_other_fields_share_one_history_event(client: TestClient, db: Session) -> None:
    roles = _org_with_roles(client, db)
    deal = _deal(client, roles["member"]).json()
    response = _patch(
        client, roles["member"], deal, forecast_category="BEST_CASE", amount="130000.00"
    )
    assert response.status_code == 200
    event = _history(client, roles["member"], deal["id"])[-1]
    assert event["changes"] == ["AMOUNT", "FORECAST_CATEGORY"]


def test_category_cannot_be_cleared_or_set_on_closed_deals(client: TestClient, db: Session) -> None:
    roles = _org_with_roles(client, db)
    deal = _deal(client, roles["member"]).json()
    cleared = _patch(client, roles["member"], deal, forecast_category=None)
    assert cleared.status_code == 422
    assert "always have a forecast category" in cleared.json()["detail"]

    lost = _stage(client, roles["member"], deal, stage="CLOSED_LOST", lost_reason="Gone").json()
    won = _stage(
        client, roles["member"], _deal(client, roles["member"]).json(), stage="CLOSED_WON"
    ).json()
    for closed in (lost, won):
        for value in ("COMMIT", None):
            response = _patch(client, roles["owner"], closed, forecast_category=value)
            assert response.status_code == 422
            assert "no forecast category" in response.json()["detail"]
    assert (
        client.get(f"/api/v1/deals/{deal['id']}", headers=_headers(roles["owner"])).json()[
            "revision"
        ]
        == lost["revision"]
    )


def test_stale_category_change_conflicts_and_changes_nothing(
    client: TestClient, db: Session
) -> None:
    roles = _org_with_roles(client, db)
    deal = _deal(client, roles["member"]).json()
    assert _patch(client, roles["owner"], deal, forecast_category="BEST_CASE").status_code == 200
    stale = _patch(client, roles["member"], deal, forecast_category="COMMIT")
    assert stale.status_code == 409
    assert stale.json()["current_revision"] == deal["revision"] + 1
    current = client.get(f"/api/v1/deals/{deal['id']}", headers=_headers(roles["member"])).json()
    assert current["forecast_category"] == "BEST_CASE"


def test_open_stage_moves_keep_the_category(client: TestClient, db: Session) -> None:
    roles = _org_with_roles(client, db)
    deal = _deal(client, roles["member"], forecast_category="COMMIT").json()
    for stage in ("DISCOVERY", "NEGOTIATION", "QUALIFICATION"):
        deal = _stage(client, roles["member"], deal, stage=stage).json()
        assert deal["forecast_category"] == "COMMIT"
    for event in _history(client, roles["member"], deal["id"])[1:]:
        assert event["changes"] == ["STAGE"]
        assert event["previous_forecast_category"] == event["new_forecast_category"] == "COMMIT"

    moved = _stage(client, roles["member"], deal, stage="PROPOSAL", forecast_category="BEST_CASE")
    assert moved.status_code == 200
    assert moved.json()["forecast_category"] == "BEST_CASE"
    assert _history(client, roles["member"], deal["id"])[-1]["changes"] == [
        "STAGE",
        "FORECAST_CATEGORY",
    ]


def test_closing_clears_and_reopening_restores_a_category(client: TestClient, db: Session) -> None:
    roles = _org_with_roles(client, db)
    deal = _deal(client, roles["member"], forecast_category="COMMIT").json()
    rejected = _stage(client, roles["member"], deal, stage="CLOSED_WON", forecast_category="COMMIT")
    assert rejected.status_code == 422

    won = _stage(client, roles["member"], deal, stage="CLOSED_WON").json()
    assert won["forecast_category"] is None
    closing = _history(client, roles["member"], deal["id"])[-1]
    assert (closing["previous_forecast_category"], closing["new_forecast_category"]) == (
        "COMMIT",
        None,
    )

    # Reopening a won deal stays manager-only; it restarts at the default category.
    assert _stage(client, roles["member"], won, stage="PROPOSAL").status_code == 403
    reopened = _stage(client, roles["admin"], won, stage="PROPOSAL").json()
    assert reopened["forecast_category"] == "PIPELINE"

    lost = _stage(client, roles["member"], reopened, stage="CLOSED_LOST", lost_reason="x").json()
    assert lost["forecast_category"] is None
    again = _stage(client, roles["member"], lost, stage="NEGOTIATION", forecast_category="COMMIT")
    assert again.status_code == 200
    assert again.json()["forecast_category"] == "COMMIT"


def test_same_stage_requests_with_a_category_point_to_patch(
    client: TestClient, db: Session
) -> None:
    roles = _org_with_roles(client, db)
    deal = _deal(client, roles["member"]).json()
    response = _stage(
        client, roles["member"], deal, stage="QUALIFICATION", forecast_category="COMMIT"
    )
    assert response.status_code == 422
    assert "use PATCH" in response.json()["detail"]


def test_won_amount_corrections_leave_the_category_empty(client: TestClient, db: Session) -> None:
    roles = _org_with_roles(client, db)
    deal = _deal(client, roles["member"], forecast_category="BEST_CASE").json()
    won = _stage(client, roles["member"], deal, stage="CLOSED_WON").json()
    corrected = client.post(
        f"/api/v1/deals/{won['id']}/amount-correction",
        json={"expected_revision": won["revision"], "amount": "1.00", "reason": "Credit note"},
        headers=_headers(roles["owner"]),
    )
    assert corrected.status_code == 200
    assert corrected.json()["forecast_category"] is None
    event = _history(client, roles["owner"], won["id"])[-1]
    assert event["changes"] == ["AMOUNT"]
    assert event["previous_forecast_category"] is None
    assert event["new_forecast_category"] is None


def test_deals_list_filters_by_category(client: TestClient, db: Session) -> None:
    roles = _org_with_roles(client, db)
    token = roles["member"]
    commit = _deal(client, token, name="Commit deal", forecast_category="COMMIT").json()
    _deal(client, token, name="Best case deal", forecast_category="BEST_CASE")
    _deal(client, token, name="Pipeline deal")
    won = _deal(client, token, name="Won deal", forecast_category="COMMIT").json()
    _stage(client, token, won, stage="CLOSED_WON")

    page = _list(client, token, forecast_category="COMMIT").json()
    assert [item["id"] for item in page["items"]] == [commit["id"]]
    assert page["total"] == 1
    assert _list(client, token, forecast_category="PIPELINE").json()["total"] == 1
    # Combines with other filters.
    assert _list(client, token, forecast_category="COMMIT", stage="PROPOSAL").json()["total"] == 0
    assert _list(client, token).json()["total"] == 4


def test_categories_are_isolated_between_organizations(client: TestClient) -> None:
    org_a = _auth(client, email="a@example.com", organization_name="Org A")
    org_b = _auth(client, email="b@example.com", organization_name="Org B")
    deal = _deal(client, org_a["access_token"], forecast_category="COMMIT").json()
    token_b = org_b["access_token"]
    assert _patch(client, token_b, deal, forecast_category="PIPELINE").status_code == 404
    assert _list(client, token_b, forecast_category="COMMIT").json()["total"] == 0
    unchanged = client.get(
        f"/api/v1/deals/{deal['id']}", headers=_headers(org_a["access_token"])
    ).json()
    assert (unchanged["forecast_category"], unchanged["revision"]) == ("COMMIT", 1)


def test_forecast_figures_do_not_depend_on_categories(client: TestClient, db: Session) -> None:
    roles = _org_with_roles(client, db)
    token = roles["owner"]
    deals = [
        _deal(client, token, amount=amount, expected_close_date=close, stage=stage).json()
        for amount, close, stage in (
            ("1000.00", "2026-12-15", "PROPOSAL"),
            ("2500.55", "2027-02-01", "NEGOTIATION"),
            ("333.33", "2027-05-20", "DISCOVERY"),
        )
    ]

    category_fields = {"category_totals", "commit_scenario_amount", "best_case_scenario_amount"}

    def without_categories(value: Any) -> Any:
        if isinstance(value, dict):
            return {k: without_categories(v) for k, v in value.items() if k not in category_fields}
        if isinstance(value, list):
            return [without_categories(item) for item in value]
        return value

    def forecast() -> dict[str, Any]:
        body = client.get(
            "/api/v1/pipeline/forecast",
            params={"granularity": "quarter", "periods": 4},
            headers=_headers(token),
        ).json()
        body.pop("as_of")
        return dict(body)

    before = forecast()
    for deal, category in zip(deals, ("COMMIT", "BEST_CASE", "COMMIT"), strict=True):
        assert _patch(client, token, deal, forecast_category=category).status_code == 200
    after = forecast()
    # Categories only regroup deals: every weighted and projected figure is unchanged.
    assert without_categories(after) == without_categories(before)
    assert (before["commit_scenario_amount"], after["commit_scenario_amount"]) == (
        "0.00",
        "1333.33",
    )
    assert after["best_case_scenario_amount"] == "3833.88"


def _raw_org(db: Session) -> Organization:
    organization = Organization(name="Raw", slug="raw-categories")
    db.add(organization)
    db.commit()
    return organization


def _raw_deal(organization: Organization, **overrides: Any) -> Deal:
    values: dict[str, Any] = {
        "organization_id": organization.id,
        "name": "Raw",
        "amount": Decimal("1.00"),
        "currency": "INR",
        "stage": "QUALIFICATION",
        "expected_close_date": date(2026, 12, 1),
        "revision": 1,
        "stage_entered_at": datetime.now(UTC),
    }
    values.update(overrides)
    return Deal(**values)


def test_insert_default_follows_the_stage(db: Session) -> None:
    organization = _raw_org(db)
    open_deal = _raw_deal(organization)
    won_deal = _raw_deal(organization, stage="CLOSED_WON", closed_at=datetime.now(UTC))
    db.add_all([open_deal, won_deal])
    db.commit()
    assert open_deal.forecast_category == "PIPELINE"
    assert won_deal.forecast_category is None


def test_database_allows_only_known_category_values(db: Session) -> None:
    organization = _raw_org(db)
    db.add(_raw_deal(organization, forecast_category="CLOSED"))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_schema_is_the_036_expand_step_without_the_open_only_check() -> None:
    names = {constraint.name for constraint in Deal.__table__.constraints}
    assert "ck_deals_forecast_category" in names
    # Deferred to the contract migration that runs after this release is serving.
    assert "ck_deals_forecast_category_open_only" not in names


# The release before migration 036 knows nothing of forecast_category: it never names
# the column on insert and never changes it on a stage change. These run its SQL
# against this schema (the same as after migration 036) to show nothing blocks it.

_OLD_RELEASE_INSERT = (
    "INSERT INTO deals (id, organization_id, name, amount, currency, stage, "
    "expected_close_date, closed_at, lost_reason, revision, stage_entered_at, created_at, "
    "updated_at) VALUES (:id, :org, 'Old release', '10.00', 'INR', :stage, '2026-12-01', "
    ":closed_at, :lost_reason, 1, '2026-10-29 00:00:00', '2026-10-29 00:00:00', "
    "'2026-10-29 00:00:00')"
)


def _old_release_insert(db: Session, org_id: str, deal_id: str, stage: str = "PROPOSAL") -> None:
    closed = stage in ("CLOSED_WON", "CLOSED_LOST")
    db.execute(
        text(_OLD_RELEASE_INSERT),
        {
            "id": deal_id,
            "org": org_id,
            "stage": stage,
            "closed_at": "2026-10-29 00:00:00" if closed else None,
            "lost_reason": "Budget" if stage == "CLOSED_LOST" else None,
        },
    )
    db.commit()


def _stored(db: Session, deal_id: str) -> tuple[str, str | None]:
    row = db.execute(
        text("SELECT stage, forecast_category FROM deals WHERE id = :id"), {"id": deal_id}
    ).one()
    return row[0], row[1]


def test_previous_release_creates_open_deals_without_a_category(db: Session) -> None:
    organization = _raw_org(db)
    _old_release_insert(db, organization.id, "old-open")
    assert _stored(db, "old-open") == ("PROPOSAL", None)


@pytest.mark.parametrize("stage", ["CLOSED_WON", "CLOSED_LOST"])
def test_previous_release_closes_deals_without_clearing_the_category(
    db: Session, stage: str
) -> None:
    organization = _raw_org(db)
    deal = _raw_deal(organization, forecast_category="COMMIT")
    db.add(deal)
    db.commit()
    db.execute(
        text(
            "UPDATE deals SET stage = :stage, closed_at = '2026-10-29 00:00:00', "
            "lost_reason = :reason, revision = revision + 1 WHERE id = :id"
        ),
        {"stage": stage, "reason": "Budget" if stage == "CLOSED_LOST" else None, "id": deal.id},
    )
    # Its history row names no category, which the history CHECKs accept.
    db.execute(
        text(
            "INSERT INTO deal_stage_events (id, organization_id, deal_id, previous_stage, "
            "new_stage, new_amount, new_expected_close_date, is_correction, created_at) VALUES "
            "(:event, :org, :id, 'QUALIFICATION', :stage, 1.00, '2026-12-01', 0, "
            "'2026-10-29 00:00:00')"
        ),
        {"event": f"event-{stage}", "org": organization.id, "id": deal.id, "stage": stage},
    )
    db.commit()
    assert _stored(db, deal.id) == (stage, "COMMIT")


def test_previous_release_reopens_closed_deals_without_a_category(db: Session) -> None:
    organization = _raw_org(db)
    _old_release_insert(db, organization.id, "old-won", stage="CLOSED_WON")
    db.execute(
        text(
            "UPDATE deals SET stage = 'NEGOTIATION', closed_at = NULL, lost_reason = NULL, "
            "revision = revision + 1 WHERE id = 'old-won'"
        )
    )
    db.commit()
    assert _stored(db, "old-won") == ("NEGOTIATION", None)


@pytest.mark.parametrize(
    "overrides",
    [
        {"new_forecast_category": "OMITTED"},
        {"new_stage": "CLOSED_LOST", "new_forecast_category": "COMMIT"},
        {"previous_stage": "CLOSED_WON", "previous_forecast_category": "PIPELINE"},
    ],
)
def test_database_rejects_inconsistent_category_history(
    db: Session, overrides: dict[str, Any]
) -> None:
    organization = _raw_org(db)
    deal = _raw_deal(organization)
    db.add(deal)
    db.commit()
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


@pytest.mark.parametrize(
    ("stage", "detail"),
    [("PROPOSAL", "always have a forecast category"), ("CLOSED_WON", "no forecast category")],
)
def test_explicit_null_is_rejected_on_create_and_stage_change(
    client: TestClient, db: Session, stage: str, detail: str
) -> None:
    roles = _org_with_roles(client, db)
    created = _deal(client, roles["owner"], stage=stage, forecast_category=None)
    assert created.status_code == 422
    assert detail in created.json()["detail"]
    # Omitting it still takes the default (PIPELINE when open, none when closed).
    assert _deal(client, roles["owner"], stage=stage).status_code == 201

    deal = _deal(client, roles["member"]).json()
    moved = _stage(client, roles["member"], deal, stage=stage, forecast_category=None)
    assert moved.status_code == 422
    assert detail in moved.json()["detail"]
    assert len(_history(client, roles["member"], deal["id"])) == 1


def test_a_refused_patch_leaves_the_category_unchanged(client: TestClient, db: Session) -> None:
    roles = _org_with_roles(client, db)
    deal = _deal(client, roles["member"]).json()
    # Permission failure after the category was applied in memory.
    forbidden = _patch(
        client, roles["member"], deal, forecast_category="COMMIT", owner_user_id=roles["admin_id"]
    )
    assert forbidden.status_code == 403
    # Validation failure after the category was applied in memory.
    invalid = _patch(client, roles["member"], deal, forecast_category="COMMIT", lost_reason="x")
    assert invalid.status_code == 422
    current = client.get(f"/api/v1/deals/{deal['id']}", headers=_headers(roles["member"])).json()
    assert (current["forecast_category"], current["revision"]) == ("PIPELINE", 1)
    assert len(_history(client, roles["member"], deal["id"])) == 1


# Rows the previous release writes during the rollout, read and written by this release.


def test_open_deals_without_a_category_read_as_pipeline(client: TestClient, db: Session) -> None:
    roles = _org_with_roles(client, db)
    _old_release_insert(db, roles["org_id"], "old-open")
    token = roles["member"]
    deal = client.get("/api/v1/deals/old-open", headers=_headers(token)).json()
    assert deal["forecast_category"] == "PIPELINE"
    pipeline = client.get(
        "/api/v1/deals", params={"forecast_category": "PIPELINE"}, headers=_headers(token)
    ).json()
    assert [item["id"] for item in pipeline["items"]] == ["old-open"]
    commit = client.get(
        "/api/v1/deals", params={"forecast_category": "COMMIT"}, headers=_headers(token)
    ).json()
    assert commit["total"] == 0

    changed = _patch(client, token, deal, forecast_category="COMMIT").json()
    assert changed["forecast_category"] == "COMMIT"
    event = _history(client, token, "old-open")[-1]
    assert (event["previous_forecast_category"], event["new_forecast_category"]) == (
        "PIPELINE",
        "COMMIT",
    )


def test_untouched_writes_repair_a_missing_category(client: TestClient, db: Session) -> None:
    roles = _org_with_roles(client, db)
    _old_release_insert(db, roles["org_id"], "old-open")
    deal = client.get("/api/v1/deals/old-open", headers=_headers(roles["member"])).json()
    renamed = _patch(client, roles["member"], deal, name="Renamed")
    assert renamed.status_code == 200
    db.expire_all()
    assert _stored(db, "old-open") == ("PROPOSAL", "PIPELINE")
    # A name change is not a category change.
    assert _history(client, roles["member"], "old-open") == []


def test_closed_deals_with_a_stale_category_read_as_none_and_reopen(
    client: TestClient, db: Session
) -> None:
    roles = _org_with_roles(client, db)
    deal = _deal(client, roles["member"], forecast_category="COMMIT").json()
    won = _stage(client, roles["member"], deal, stage="CLOSED_WON").json()
    # Simulate the previous release closing it: the category is left behind.
    db.execute(
        text("UPDATE deals SET forecast_category = 'COMMIT' WHERE id = :id"), {"id": deal["id"]}
    )
    db.commit()

    current = client.get(f"/api/v1/deals/{deal['id']}", headers=_headers(roles["owner"])).json()
    assert current["forecast_category"] is None
    listed = client.get(
        "/api/v1/deals", params={"forecast_category": "COMMIT"}, headers=_headers(roles["owner"])
    ).json()
    assert listed["total"] == 0

    reopened = _stage(client, roles["admin"], won, stage="PROPOSAL")
    assert reopened.status_code == 200, reopened.text
    assert reopened.json()["forecast_category"] == "PIPELINE"
    event = _history(client, roles["owner"], deal["id"])[-1]
    assert (event["previous_forecast_category"], event["new_forecast_category"]) == (
        None,
        "PIPELINE",
    )


def test_won_corrections_repair_a_stale_category(client: TestClient, db: Session) -> None:
    roles = _org_with_roles(client, db)
    deal = _deal(client, roles["member"]).json()
    won = _stage(client, roles["member"], deal, stage="CLOSED_WON").json()
    db.execute(
        text("UPDATE deals SET forecast_category = 'BEST_CASE' WHERE id = :id"),
        {"id": deal["id"]},
    )
    db.commit()
    corrected = client.post(
        f"/api/v1/deals/{won['id']}/amount-correction",
        json={"expected_revision": won["revision"], "amount": "1.00", "reason": "Credit note"},
        headers=_headers(roles["owner"]),
    )
    assert corrected.status_code == 200, corrected.text
    db.expire_all()
    assert _stored(db, deal["id"]) == ("CLOSED_WON", None)

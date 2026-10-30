"""PostgreSQL-only checks for migration 034 and the constraints SQLite cannot prove.

Every test works in its own schema and drops it afterwards.
"""

import os
import subprocess
import sys
import threading
import time
from collections.abc import Generator
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import DataError, IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.core.exceptions import ConflictError, ForbiddenError
from app.core.rate_limit import website_capture_limiter
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.deal import Deal, DealStage, DealStageEvent, ForecastCategory
from app.models.lead import Lead
from app.models.membership import Membership, MembershipRole
from app.models.organization import Organization
from app.models.sales_target import SalesTarget
from app.models.user import User
from app.schemas.deals import (
    DealAmountCorrectionRequest,
    DealCreate,
    DealStageChangeRequest,
    DealUpdate,
)
from app.schemas.pipeline import ForecastGranularity
from app.services.deal_service import DealService
from app.services.pipeline_service import PipelineService
from tests.test_inbound_qualification_claim_postgres import _postgres_reachable

pytestmark = pytest.mark.skipif(
    not _postgres_reachable(),
    reason="PostgreSQL is not reachable",
)

BACKEND_DIR = Path(__file__).resolve().parents[1]


def _schema_url(schema: str) -> str:
    separator = "&" if "?" in settings.database_url else "?"
    return f"{settings.database_url}{separator}options=-csearch_path%3D{schema}"


@pytest.fixture
def schema() -> Generator[str, None, None]:
    name = f"deals_test_{uuid4().hex[:10]}"
    admin = create_engine(settings.database_url)
    with admin.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{name}"'))
    try:
        yield name
    finally:
        with admin.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{name}" CASCADE'))
        admin.dispose()


@pytest.fixture
def pg_engine(schema: str) -> Generator[Any, None, None]:
    engine = create_engine(
        settings.database_url,
        connect_args={"options": f"-csearch_path={schema}"},
    )
    Base.metadata.create_all(bind=engine)
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture
def pg_session(pg_engine: Any) -> Generator[Session, None, None]:
    session = sessionmaker(bind=pg_engine, expire_on_commit=False)()
    try:
        yield session
    finally:
        session.close()


def _alembic(schema: str, *args: str) -> None:
    env = {**os.environ, "DATABASE_URL": _schema_url(schema)}
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "-c", str(BACKEND_DIR / "alembic.ini"), *args],
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert result.returncode == 0, result.stderr[-2000:]


def _org_with_owner(session: Session, name: str = "Acme") -> tuple[Organization, User]:
    organization = Organization(name=name, slug=f"{name.lower()}-{uuid4().hex[:8]}")
    user = User(email=f"{uuid4().hex[:8]}@example.com", name=f"{name} Owner", password_hash="x")
    session.add_all([organization, user])
    session.flush()
    session.add(
        Membership(organization_id=organization.id, user_id=user.id, role=MembershipRole.OWNER)
    )
    session.commit()
    return organization, user


def _deal_row(organization_id: str, **overrides: Any) -> Deal:
    now = datetime.now(UTC)
    values: dict[str, Any] = {
        "organization_id": organization_id,
        "name": "Raw deal",
        "amount": Decimal("10.00"),
        "currency": "INR",
        "stage": "QUALIFICATION",
        "expected_close_date": date(2026, 12, 1),
        "revision": 1,
        "stage_entered_at": now,
    }
    values.update(overrides)
    return Deal(**values)


def test_migration_034_upgrades_preserves_data_and_downgrades(schema: str) -> None:
    _alembic(schema, "upgrade", "033_company_prospect_activity")
    engine = create_engine(
        settings.database_url, connect_args={"options": f"-csearch_path={schema}"}
    )
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO organizations (id, name, slug, website_capture_enabled, "
                    "sales_agent_auto_start_enabled) VALUES ('org-1', 'Existing', 'existing', "
                    "false, false)"
                )
            )

        _alembic(schema, "upgrade", "034_deal_foundation")
        inspector = inspect(engine)
        tables = set(inspector.get_table_names())
        assert {"deals", "deal_stage_events", "sales_targets"} <= tables
        with engine.connect() as connection:
            assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar() == (
                "034_deal_foundation"
            )
            assert (
                connection.execute(
                    text("SELECT default_currency FROM organizations WHERE id = 'org-1'")
                ).scalar()
                == "INR"
            )
        deal_checks = {check["name"] for check in inspector.get_check_constraints("deals")}
        assert {
            "ck_deals_stage",
            "ck_deals_amount_non_negative",
            "ck_deals_currency",
            "ck_deals_probability_range",
            "ck_deals_probability_open_only",
            "ck_deals_closed_at_matches_stage",
            "ck_deals_lost_reason_lost_only",
            "ck_deals_revision_positive",
        } <= deal_checks
        deal_fks = {fk["name"] for fk in inspector.get_foreign_keys("deals")}
        assert {"fk_deals_lead_organization", "fk_deals_owner_membership"} <= deal_fks
        deal_indexes = {index["name"] for index in inspector.get_indexes("deals")}
        assert {
            "ix_deals_organization_stage",
            "ix_deals_organization_expected_close_date",
            "ix_deals_organization_owner",
            "ix_deals_organization_lead",
        } <= deal_indexes
        target_indexes = {index["name"] for index in inspector.get_indexes("sales_targets")}
        assert {
            "uq_sales_targets_organization_period",
            "uq_sales_targets_organization_owner_period",
        } <= target_indexes
        amount_type = next(
            column["type"]
            for column in inspector.get_columns("deals")
            if column["name"] == "amount"
        )
        assert (amount_type.precision, amount_type.scale) == (14, 2)

        _alembic(schema, "downgrade", "033_company_prospect_activity")
        inspector = inspect(engine)
        assert not {"deals", "deal_stage_events", "sales_targets"} & set(
            inspector.get_table_names()
        )
        org_columns = {column["name"] for column in inspector.get_columns("organizations")}
        assert "default_currency" not in org_columns
        with engine.connect() as connection:
            existing_name = connection.execute(
                text("SELECT name FROM organizations WHERE id = 'org-1'")
            ).scalar()
            assert existing_name == "Existing"

        _alembic(schema, "upgrade", "head")
        assert "deals" in set(inspect(engine).get_table_names())
    finally:
        engine.dispose()


def test_same_organization_foreign_keys_are_enforced(pg_session: Session) -> None:
    org_a, _ = _org_with_owner(pg_session, "Alpha")
    org_b, user_b = _org_with_owner(pg_session, "Beta")
    lead_b = Lead(organization_id=org_b.id, name="Beta lead")
    pg_session.add(lead_b)
    pg_session.commit()

    for overrides in ({"lead_id": lead_b.id}, {"owner_user_id": user_b.id}):
        pg_session.add(_deal_row(org_a.id, **overrides))
        with pytest.raises(IntegrityError):
            pg_session.commit()
        pg_session.rollback()

    deal = _deal_row(org_a.id)
    pg_session.add(deal)
    pg_session.commit()
    pg_session.add(
        DealStageEvent(
            organization_id=org_b.id,
            deal_id=deal.id,
            new_stage="QUALIFICATION",
            new_amount=Decimal("1.00"),
            new_expected_close_date=date(2026, 12, 1),
        )
    )
    with pytest.raises(IntegrityError):
        pg_session.commit()
    pg_session.rollback()
    pg_session.add(
        SalesTarget(
            organization_id=org_a.id,
            owner_user_id=user_b.id,
            period_start=date(2026, 11, 1),
            period_end=date(2026, 11, 30),
            amount=Decimal("1.00"),
            currency="INR",
        )
    )
    with pytest.raises(IntegrityError):
        pg_session.commit()
    pg_session.rollback()


@pytest.mark.parametrize(
    "overrides",
    [
        {"amount": Decimal("-0.01")},
        {"stage": "WON"},
        {"currency": "inr"},
        {"currency": "INRS"},
        {"probability": 101},
        {"probability": 50, "stage": "CLOSED_WON", "closed_at": datetime.now(UTC)},
        {"stage": "CLOSED_WON"},
        {"closed_at": datetime.now(UTC)},
        {"lost_reason": "No budget"},
        {"revision": 0},
    ],
)
def test_check_constraints_are_enforced(pg_session: Session, overrides: dict[str, Any]) -> None:
    organization, _ = _org_with_owner(pg_session)
    pg_session.add(_deal_row(organization.id, **overrides))
    # Over-long codes hit VARCHAR(3) (DataError) before the CHECK (IntegrityError).
    with pytest.raises((IntegrityError, DataError)):
        pg_session.commit()
    pg_session.rollback()


def test_numeric_precision_is_exact_and_bounded(pg_session: Session) -> None:
    organization, _ = _org_with_owner(pg_session)
    for value in ("0.10", "0.20", "999999999999.99"):
        deal = _deal_row(organization.id, amount=Decimal(value))
        pg_session.add(deal)
        pg_session.commit()
        pg_session.expire(deal)
        assert deal.amount == Decimal(value)
        assert str(deal.amount) == value
    pg_session.add(_deal_row(organization.id, amount=Decimal("1000000000000.00")))
    with pytest.raises(DataError):
        pg_session.commit()
    pg_session.rollback()


def test_organization_wide_targets_are_unique_per_period(pg_session: Session) -> None:
    organization, owner = _org_with_owner(pg_session)

    def target(owner_user_id: str | None) -> SalesTarget:
        return SalesTarget(
            organization_id=organization.id,
            owner_user_id=owner_user_id,
            period_start=date(2026, 11, 1),
            period_end=date(2026, 11, 30),
            amount=Decimal("100.00"),
            currency="INR",
        )

    pg_session.add_all([target(None), target(owner.id)])
    pg_session.commit()
    for owner_user_id in (None, owner.id):
        pg_session.add(target(owner_user_id))
        with pytest.raises(IntegrityError):
            pg_session.commit()
        pg_session.rollback()


def test_concurrent_updates_with_the_same_revision_conflict(pg_engine: Any) -> None:
    factory = sessionmaker(bind=pg_engine, expire_on_commit=False)
    setup = factory()
    organization, owner = _org_with_owner(setup)
    deal = DealService(setup).create(
        organization,
        role=MembershipRole.OWNER,
        user_id=owner.id,
        payload=DealCreate(
            name="Race", amount=Decimal("1.00"), expected_close_date=date(2026, 12, 1)
        ),
    )
    setup.close()

    holder = factory()
    contender_result: dict[str, Any] = {}
    locked = holder.get(Deal, deal.id, with_for_update=True)
    assert locked is not None

    def contend() -> None:
        session = factory()
        try:
            DealService(session).update(
                organization.id,
                deal.id,
                role=MembershipRole.OWNER,
                user_id=owner.id,
                payload=DealUpdate(expected_revision=1, amount=Decimal("3.00")),
            )
            contender_result["outcome"] = "updated"
        except ConflictError as exc:
            contender_result["outcome"] = "conflict"
            contender_result["content"] = exc.content
        finally:
            session.close()

    thread = threading.Thread(target=contend)
    thread.start()
    time.sleep(0.5)
    # The contender must still be waiting on the row lock.
    assert thread.is_alive()
    locked.amount = Decimal("2.00")
    locked.revision = 2
    holder.commit()
    holder.close()
    thread.join(timeout=10)
    assert contender_result["outcome"] == "conflict"
    assert contender_result["content"] == {
        "detail": "This deal changed. Refresh and review the latest version.",
        "current_revision": 2,
    }

    check = factory()
    stored = check.get(Deal, deal.id)
    assert stored is not None
    assert stored.amount == Decimal("2.00")
    check.close()


def test_deal_lifecycle_persists_with_aware_timestamps(pg_engine: Any) -> None:
    factory = sessionmaker(bind=pg_engine, expire_on_commit=False)
    session = factory()
    organization, owner = _org_with_owner(session)
    lead = Lead(organization_id=organization.id, name="Converted lead")
    session.add(lead)
    session.commit()
    deal = DealService(session).create(
        organization,
        role=MembershipRole.OWNER,
        user_id=owner.id,
        payload=DealCreate(
            name="Persisted",
            amount=Decimal("4500.75"),
            expected_close_date=date(2027, 1, 15),
            lead_id=lead.id,
        ),
    )
    session.close()
    pg_engine.dispose()

    fresh = sessionmaker(bind=pg_engine, expire_on_commit=False)()
    try:
        stored = fresh.get(Deal, deal.id)
        assert stored is not None
        assert stored.amount == Decimal("4500.75")
        assert stored.created_at.tzinfo is not None
        assert stored.stage_entered_at.tzinfo is not None
        stored_lead = fresh.get(Lead, lead.id)
        assert stored_lead is not None
        assert stored_lead.status == "CONVERTED"
        history = DealService(fresh).history(organization.id, deal.id, limit=10, offset=0)
        assert [event.changes for event in history.items] == [["CREATED"]]
    finally:
        fresh.close()


@pytest.fixture
def pg_client(pg_engine: Any) -> Generator[TestClient, None, None]:
    """The real API over PostgreSQL, one session per request as in production."""
    factory = sessionmaker(bind=pg_engine, expire_on_commit=False)

    def override_get_db() -> Generator[Session, None, None]:
        session = factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    website_capture_limiter.reset()
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.pop(get_db, None)


def _register(client: TestClient, email: str, organization: str) -> dict[str, Any]:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "password12",
            "name": f"{organization} Owner",
            "organization_name": organization,
        },
    )
    assert response.status_code in (200, 201), response.text
    return dict(response.json())


def test_deal_api_round_trip_on_postgres(pg_client: TestClient, pg_engine: Any) -> None:
    org_a = _register(pg_client, "pg-a@example.com", "PG Alpha")
    org_b = _register(pg_client, "pg-b@example.com", "PG Beta")
    headers_a = {"Authorization": f"Bearer {org_a['access_token']}"}
    headers_b = {"Authorization": f"Bearer {org_b['access_token']}"}
    assert org_a["organization"]["default_currency"] == "INR"

    lead = pg_client.post("/api/v1/leads", json={"name": "PG lead"}, headers=headers_a).json()
    created = pg_client.post(
        "/api/v1/deals",
        json={
            "name": "PG deal",
            "amount": "0.10",
            "expected_close_date": "2026-12-31",
            "lead_id": lead["id"],
            "probability": 30,
        },
        headers=headers_a,
    )
    assert created.status_code == 201, created.text
    deal = created.json()
    assert deal["amount"] == "0.10"
    assert deal["currency"] == "INR"
    assert deal["effective_probability"] == 30
    assert deal["created_at"].endswith(("Z", "+00:00"))
    lead_after = pg_client.get(f"/api/v1/leads/{lead['id']}", headers=headers_a).json()
    assert lead_after["status"] == "CONVERTED"

    patched = pg_client.patch(
        f"/api/v1/deals/{deal['id']}",
        json={"expected_revision": 1, "amount": "999999999999.99"},
        headers=headers_a,
    )
    assert patched.status_code == 200
    assert patched.json()["amount"] == "999999999999.99"
    stale = pg_client.patch(
        f"/api/v1/deals/{deal['id']}",
        json={"expected_revision": 1, "amount": "1.00"},
        headers=headers_a,
    )
    assert stale.status_code == 409
    won = pg_client.post(
        f"/api/v1/deals/{deal['id']}/stage",
        json={"expected_revision": 2, "stage": "CLOSED_WON"},
        headers=headers_a,
    )
    assert won.status_code == 200
    assert won.json()["effective_probability"] == 100
    assert won.json()["closed_at"] is not None

    history = pg_client.get(f"/api/v1/deals/{deal['id']}/history", headers=headers_a).json()
    assert [event["changes"] for event in history["items"]] == [
        ["CREATED"],
        ["AMOUNT"],
        # Winning clears the 30% override and the forecast category; both are recorded.
        ["STAGE", "PROBABILITY", "FORECAST_CATEGORY"],
    ]
    won_event = history["items"][2]
    assert (won_event["previous_probability"], won_event["new_probability"]) == (30, None)
    assert history["items"][1]["previous_amount"] == "0.10"
    assert history["items"][1]["new_amount"] == "999999999999.99"

    for method, path in (
        ("GET", f"/api/v1/deals/{deal['id']}"),
        ("GET", f"/api/v1/deals/{deal['id']}/history"),
    ):
        assert pg_client.request(method, path, headers=headers_b).status_code == 404
    assert pg_client.get("/api/v1/deals", headers=headers_b).json()["total"] == 0

    target = pg_client.put(
        "/api/v1/sales-targets",
        json={"period_start": "2026-12-01", "amount": "1500000.00"},
        headers=headers_a,
    )
    assert target.status_code == 201
    assert target.json()["amount"] == "1500000.00"
    assert target.json()["period_end"] == "2026-12-31"
    again = pg_client.put(
        "/api/v1/sales-targets",
        json={"period_start": "2026-12-01", "amount": "1600000.00"},
        headers=headers_a,
    )
    assert again.status_code == 200 and again.json()["id"] == target.json()["id"]
    assert pg_client.get("/api/v1/sales-targets", headers=headers_b).json()["total"] == 0

    # Everything above is read back through a brand-new connection pool.
    pg_engine.dispose()
    check = sessionmaker(bind=pg_engine)()
    try:
        stored = check.get(Deal, deal["id"])
        assert stored is not None
        assert stored.amount == Decimal("999999999999.99")
        assert stored.stage == "CLOSED_WON"
        assert check.query(DealStageEvent).filter_by(deal_id=deal["id"]).count() == 3
        assert check.query(SalesTarget).count() == 1
    finally:
        check.close()


def test_concurrent_stage_changes_with_the_same_revision_conflict(pg_engine: Any) -> None:
    factory = sessionmaker(bind=pg_engine, expire_on_commit=False)
    setup = factory()
    organization, owner = _org_with_owner(setup)
    deal = DealService(setup).create(
        organization,
        role=MembershipRole.OWNER,
        user_id=owner.id,
        payload=DealCreate(
            name="Stage race", amount=Decimal("1.00"), expected_close_date=date(2026, 12, 1)
        ),
    )
    setup.close()

    results: list[str] = []
    barrier = threading.Barrier(2)

    def move(stage: str) -> None:
        session = factory()
        try:
            barrier.wait()
            DealService(session).change_stage(
                organization.id,
                deal.id,
                role=MembershipRole.OWNER,
                user_id=owner.id,
                payload=DealStageChangeRequest(stage=stage, expected_revision=1),
            )
            results.append("moved")
        except ConflictError:
            results.append("conflict")
        finally:
            session.close()

    threads = [threading.Thread(target=move, args=(s,)) for s in ("PROPOSAL", "NEGOTIATION")]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=15)
    assert sorted(results) == ["conflict", "moved"]

    check = factory()
    try:
        stored = check.get(Deal, deal.id)
        assert stored is not None
        assert stored.revision == 2
        events = check.query(DealStageEvent).filter_by(deal_id=deal.id).count()
        assert events == 2  # creation + exactly one stage change
    finally:
        check.close()


def test_migration_035_adds_probability_history_without_rewriting_rows(schema: str) -> None:
    _alembic(schema, "upgrade", "034_deal_foundation")
    engine = create_engine(
        settings.database_url, connect_args={"options": f"-csearch_path={schema}"}
    )
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO organizations (id, name, slug, website_capture_enabled, "
                    "sales_agent_auto_start_enabled) VALUES ('org-1', 'Existing', 'existing', "
                    "false, false)"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO deals (id, organization_id, name, amount, currency, stage, "
                    "probability, expected_close_date, revision, stage_entered_at) VALUES "
                    "('deal-1', 'org-1', 'Old', 10.00, 'INR', 'DISCOVERY', 40, '2026-12-01', 1, "
                    "now())"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO deal_stage_events (id, organization_id, deal_id, new_stage, "
                    "new_amount, new_expected_close_date) VALUES ('event-1', 'org-1', 'deal-1', "
                    "'DISCOVERY', 10.00, '2026-12-01')"
                )
            )

        _alembic(schema, "upgrade", "035_deal_history_probability")
        inspector = inspect(engine)
        columns = {column["name"] for column in inspector.get_columns("deal_stage_events")}
        assert {"previous_probability", "new_probability", "is_correction"} <= columns
        checks = {check["name"] for check in inspector.get_check_constraints("deal_stage_events")}
        assert {
            "ck_deal_stage_events_probability_range",
            "ck_deal_stage_events_probability_open_only",
            "ck_deal_stage_events_correction_won_only",
        } <= checks
        assert "ix_deals_organization_closed_at" in {
            index["name"] for index in inspector.get_indexes("deals")
        }
        with engine.connect() as connection:
            row = connection.execute(
                text(
                    "SELECT previous_probability, new_probability, is_correction "
                    "FROM deal_stage_events WHERE id = 'event-1'"
                )
            ).one()
            # The historical override is unknown, so nothing is backfilled.
            assert tuple(row) == (None, None, False)
            assert (
                connection.execute(
                    text("SELECT probability FROM deals WHERE id = 'deal-1'")
                ).scalar()
                == 40
            )
        with engine.begin() as connection, pytest.raises(IntegrityError):
            connection.execute(
                text(
                    "INSERT INTO deal_stage_events (id, organization_id, deal_id, "
                    "previous_stage, new_stage, new_amount, new_expected_close_date, "
                    "is_correction, change_reason) VALUES ('event-2', 'org-1', 'deal-1', "
                    "'DISCOVERY', 'DISCOVERY', 10.00, '2026-12-01', true, 'Not won')"
                )
            )

        _alembic(schema, "downgrade", "034_deal_foundation")
        inspector = inspect(engine)
        columns = {column["name"] for column in inspector.get_columns("deal_stage_events")}
        assert not {"previous_probability", "new_probability", "is_correction"} & columns
        assert "ix_deals_organization_closed_at" not in {
            index["name"] for index in inspector.get_indexes("deals")
        }
        with engine.connect() as connection:
            assert connection.execute(text("SELECT count(*) FROM deal_stage_events")).scalar() == 1
        _alembic(schema, "upgrade", "head")
    finally:
        engine.dispose()


_ALL_STAGES = (
    "QUALIFICATION",
    "DISCOVERY",
    "PROPOSAL",
    "NEGOTIATION",
    "CLOSED_WON",
    "CLOSED_LOST",
)


def test_migration_036_backfills_open_deals_and_keeps_history(schema: str) -> None:
    _alembic(schema, "upgrade", "035_deal_history_probability")
    engine = create_engine(
        settings.database_url, connect_args={"options": f"-csearch_path={schema}"}
    )
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO organizations (id, name, slug, website_capture_enabled, "
                    "sales_agent_auto_start_enabled) VALUES ('org-1', 'Existing', 'existing', "
                    "false, false)"
                )
            )
            for stage in _ALL_STAGES:
                closed = stage.startswith("CLOSED_")
                connection.execute(
                    text(
                        "INSERT INTO deals (id, organization_id, name, amount, currency, stage, "
                        "expected_close_date, closed_at, lost_reason, revision, "
                        "stage_entered_at) VALUES (:id, 'org-1', 'Old', 10.00, 'INR', :stage, "
                        "'2026-12-01', :closed_at, :lost_reason, 3, now())"
                    ),
                    {
                        "id": stage.lower(),
                        "stage": stage,
                        "closed_at": datetime(2026, 10, 1, tzinfo=UTC) if closed else None,
                        "lost_reason": "Budget" if stage == "CLOSED_LOST" else None,
                    },
                )
            # History rows recorded before 036: a creation, and closing events.
            for event_id, deal_id, previous, new in (
                ("event-created", "qualification", None, "QUALIFICATION"),
                ("event-won", "closed_won", "NEGOTIATION", "CLOSED_WON"),
                ("event-lost", "closed_lost", "PROPOSAL", "CLOSED_LOST"),
            ):
                connection.execute(
                    text(
                        "INSERT INTO deal_stage_events (id, organization_id, deal_id, "
                        "previous_stage, new_stage, new_amount, new_expected_close_date) "
                        "VALUES (:id, 'org-1', :deal, :previous, :new, 10.00, '2026-12-01')"
                    ),
                    {"id": event_id, "deal": deal_id, "previous": previous, "new": new},
                )
            history_before = connection.execute(
                text("SELECT * FROM deal_stage_events ORDER BY id")
            ).all()

        _alembic(schema, "upgrade", "036_deal_forecast_category")
        inspector = inspect(engine)
        assert "forecast_category" in {c["name"] for c in inspector.get_columns("deals")}
        assert {"previous_forecast_category", "new_forecast_category"} <= {
            c["name"] for c in inspector.get_columns("deal_stage_events")
        }
        deal_checks = {check["name"] for check in inspector.get_check_constraints("deals")}
        assert "ck_deals_forecast_category" in deal_checks
        # Expand step only: the open-only rule waits for the contract migration.
        assert "ck_deals_forecast_category_open_only" not in deal_checks
        assert {
            "ck_deal_stage_events_forecast_category",
            "ck_deal_stage_events_forecast_category_open_only",
        } <= {check["name"] for check in inspector.get_check_constraints("deal_stage_events")}
        with engine.connect() as connection:
            rows = dict(
                connection.execute(text("SELECT stage, forecast_category FROM deals")).all()
            )
            assert rows == {
                "QUALIFICATION": "PIPELINE",
                "DISCOVERY": "PIPELINE",
                "PROPOSAL": "PIPELINE",
                "NEGOTIATION": "PIPELINE",
                "CLOSED_WON": None,
                "CLOSED_LOST": None,
            }
            # Only the new column is written: revisions and history stay as they were.
            assert set(
                connection.execute(text("SELECT DISTINCT revision FROM deals")).scalars()
            ) == {3}
            history_after = connection.execute(
                text(
                    "SELECT previous_forecast_category, new_forecast_category "
                    "FROM deal_stage_events ORDER BY id"
                )
            ).all()
            assert [tuple(row) for row in history_after] == [(None, None)] * 3
            original_columns = connection.execute(
                text(
                    "SELECT id, organization_id, deal_id, previous_stage, new_stage, new_amount, "
                    "new_expected_close_date, created_at FROM deal_stage_events ORDER BY id"
                )
            ).all()
            assert [tuple(row) for row in original_columns] == [
                (
                    r.id,
                    r.organization_id,
                    r.deal_id,
                    r.previous_stage,
                    r.new_stage,
                    r.new_amount,
                    r.new_expected_close_date,
                    r.created_at,
                )
                for r in history_before
            ]

        # The previous release keeps serving after this migration. Its writes never name
        # forecast_category; every one of them must still succeed.
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO deals (id, organization_id, name, amount, currency, stage, "
                    "expected_close_date, revision, stage_entered_at) VALUES ('old-new', "
                    "'org-1', 'New', 5.00, 'INR', 'DISCOVERY', '2026-12-01', 1, now())"
                )
            )
            connection.execute(
                text(
                    "UPDATE deals SET stage = 'CLOSED_WON', closed_at = now() WHERE id = 'proposal'"
                )
            )
            connection.execute(
                text(
                    "UPDATE deals SET stage = 'CLOSED_LOST', closed_at = now(), "
                    "lost_reason = 'Budget' WHERE id = 'negotiation'"
                )
            )
            connection.execute(
                text(
                    "UPDATE deals SET stage = 'PROPOSAL', closed_at = NULL, lost_reason = NULL "
                    "WHERE id = 'closed_lost'"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO deal_stage_events (id, organization_id, deal_id, "
                    "previous_stage, new_stage, new_amount, new_expected_close_date) VALUES "
                    "('event-old-close', 'org-1', 'proposal', 'PROPOSAL', 'CLOSED_WON', 10.00, "
                    "'2026-12-01')"
                )
            )
        with engine.connect() as connection:
            assert dict(
                connection.execute(
                    text(
                        "SELECT id, forecast_category FROM deals WHERE id IN "
                        "('old-new', 'proposal', 'negotiation', 'closed_lost')"
                    )
                ).all()
            ) == {
                "old-new": None,
                "proposal": "PIPELINE",
                "negotiation": "PIPELINE",
                "closed_lost": None,
            }
        with engine.begin() as connection, pytest.raises(IntegrityError):
            connection.execute(
                text("UPDATE deals SET forecast_category = 'OMITTED' WHERE id = 'discovery'")
            )

        _alembic(schema, "downgrade", "035_deal_history_probability")
        inspector = inspect(engine)
        assert "forecast_category" not in {c["name"] for c in inspector.get_columns("deals")}
        assert not {"previous_forecast_category", "new_forecast_category"} & {
            c["name"] for c in inspector.get_columns("deal_stage_events")
        }
        with engine.connect() as connection:
            assert connection.execute(text("SELECT count(*) FROM deals")).scalar() == 7
            assert connection.execute(text("SELECT count(*) FROM deal_stage_events")).scalar() == 4
        _alembic(schema, "upgrade", "head")
    finally:
        engine.dispose()


def test_concurrent_category_changes_with_the_same_revision_conflict(pg_engine: Any) -> None:
    factory = sessionmaker(bind=pg_engine, expire_on_commit=False)
    setup = factory()
    organization, owner = _org_with_owner(setup)
    deal = DealService(setup).create(
        organization,
        role=MembershipRole.MEMBER,
        user_id=owner.id,
        payload=DealCreate(
            name="Race", amount=Decimal("1.00"), expected_close_date=date(2026, 12, 1)
        ),
    )
    setup.close()

    holder = factory()
    contender_result: dict[str, Any] = {}
    locked = holder.get(Deal, deal.id, with_for_update=True)
    assert locked is not None

    def contend() -> None:
        session = factory()
        try:
            DealService(session).update(
                organization.id,
                deal.id,
                role=MembershipRole.MEMBER,
                user_id=owner.id,
                payload=DealUpdate(expected_revision=1, forecast_category="BEST_CASE"),
            )
            contender_result["outcome"] = "updated"
        except ConflictError:
            contender_result["outcome"] = "conflict"
        finally:
            session.close()

    thread = threading.Thread(target=contend)
    thread.start()
    time.sleep(0.5)
    assert thread.is_alive()  # waiting on the row lock
    locked.forecast_category = "COMMIT"
    locked.revision = 2
    holder.commit()
    holder.close()
    thread.join(timeout=10)
    assert contender_result["outcome"] == "conflict"

    check = factory()
    stored = check.get(Deal, deal.id)
    assert stored is not None
    assert (stored.forecast_category, stored.revision) == ("COMMIT", 2)
    # The losing writer recorded nothing.
    events = check.query(DealStageEvent).filter_by(deal_id=deal.id).all()
    assert [(e.previous_forecast_category, e.new_forecast_category) for e in events] == [
        (None, "PIPELINE")
    ]
    check.close()


def test_forecast_category_lifecycle_on_postgres(pg_engine: Any) -> None:
    session = sessionmaker(bind=pg_engine, expire_on_commit=False)()
    try:
        organization, user = _org_with_owner(session)
        service = DealService(session)
        deal = service.create(
            organization,
            role=MembershipRole.MEMBER,
            user_id=user.id,
            payload=DealCreate(
                name="Category", amount=Decimal("10.00"), expected_close_date=date(2026, 12, 1)
            ),
        )
        assert deal.forecast_category == "PIPELINE"
        deal = service.update(
            organization.id,
            deal.id,
            role=MembershipRole.MEMBER,
            user_id=user.id,
            payload=DealUpdate(expected_revision=deal.revision, forecast_category="COMMIT"),
        )
        deal = service.change_stage(
            organization.id,
            deal.id,
            role=MembershipRole.MEMBER,
            user_id=user.id,
            payload=DealStageChangeRequest(stage="CLOSED_WON", expected_revision=deal.revision),
        )
        assert deal.forecast_category is None
        history = [
            (row.previous_forecast_category, row.new_forecast_category)
            for row in session.query(DealStageEvent)
            .filter_by(deal_id=deal.id)
            .order_by(DealStageEvent.created_at, DealStageEvent.id)
        ]
        assert history == [(None, "PIPELINE"), ("PIPELINE", "COMMIT"), ("COMMIT", None)]
    finally:
        session.close()


def test_forecast_buckets_in_utc_regardless_of_session_timezone(pg_session: Session) -> None:
    organization, _ = _org_with_owner(pg_session)
    pg_session.execute(text("SET TIME ZONE 'Asia/Kolkata'"))
    now = datetime(2026, 3, 15, 12, tzinfo=UTC)

    def won(amount: str, closed_at: datetime) -> Deal:
        return _deal_row(
            organization.id,
            amount=Decimal(amount),
            stage="CLOSED_WON",
            closed_at=closed_at,
            stage_entered_at=closed_at,
        )

    pg_session.add_all(
        [
            _deal_row(
                organization.id, amount=Decimal("1.00"), expected_close_date=date(2026, 3, 14)
            ),
            _deal_row(
                organization.id, amount=Decimal("2.00"), expected_close_date=date(2026, 3, 31)
            ),
            _deal_row(
                organization.id,
                amount=Decimal("999999999999.99"),
                stage="NEGOTIATION",
                expected_close_date=date(2026, 4, 1),
            ),
            _deal_row(
                organization.id,
                amount=Decimal("333.33"),
                probability=33,
                expected_close_date=date(2026, 6, 30),
            ),
            _deal_row(
                organization.id, amount=Decimal("8.00"), expected_close_date=date(2026, 7, 1)
            ),
            # 05:00 IST on 1 March is still February in UTC.
            won("100.00", datetime(2026, 2, 28, 23, 30, tzinfo=UTC)),
            won("200.00", datetime(2026, 3, 1, tzinfo=UTC)),
            won("400.00", datetime(2026, 6, 30, 23, 59, 59, tzinfo=UTC)),
            _deal_row(organization.id, amount=Decimal("9.00"), currency="USD"),
        ]
    )
    pg_session.commit()

    service = PipelineService(pg_session)
    months = service.forecast(
        organization.id, granularity=ForecastGranularity.MONTH, periods=4, now=now
    )
    assert [(p.label, p.open.total_amount, p.won.total_amount) for p in months.periods] == [
        ("2026-03", Decimal("2.00"), Decimal("200.00")),
        ("2026-04", Decimal("999999999999.99"), Decimal("0.00")),
        ("2026-05", Decimal("0.00"), Decimal("0.00")),
        ("2026-06", Decimal("333.33"), Decimal("400.00")),
    ]
    assert months.periods[1].open.weighted_amount == Decimal("749999999999.99")
    assert months.periods[3].open.weighted_amount == Decimal("110.00")
    assert months.past_due.total_amount == Decimal("1.00")
    assert months.past_due.oldest_expected_close_date == date(2026, 3, 14)
    assert months.beyond_horizon.total_amount == Decimal("8.00")
    # 0.10 + 0.20 + 749999999999.99 + 110.00 + 0.80 (past due and beyond included).
    assert months.open_pipeline.weighted_amount == Decimal("750000000111.09")
    assert months.excluded_other_currency_count == 1

    quarters = service.forecast(
        organization.id, granularity=ForecastGranularity.QUARTER, periods=2, now=now
    )
    assert [(p.label, p.won.total_amount) for p in quarters.periods] == [
        ("2026-Q1", Decimal("300.00")),  # January-March includes the 28 February win
        ("2026-Q2", Decimal("400.00")),
    ]
    # Won 700.00 + weighted in Q1-Q2 (0.20 + 749999999999.99 + 110.00); past due excluded.
    assert quarters.projected_in_horizon_amount == Decimal("750000000810.19")

    summary = service.summary(organization.id, months=2, now=now)
    assert [(m.month, m.total_amount) for m in summary.won_by_month] == [
        (date(2026, 2, 1), Decimal("100.00")),
        (date(2026, 3, 1), Decimal("200.00")),
    ]
    assert summary.open.weighted_amount == months.open_pipeline.weighted_amount


def test_forecast_category_totals_and_scenarios_on_postgres(pg_session: Session) -> None:
    organization, _ = _org_with_owner(pg_session)
    other, _ = _org_with_owner(pg_session, name="Other")
    now = datetime(2026, 3, 15, 12, tzinfo=UTC)
    pg_session.add_all(
        [
            _deal_row(
                organization.id,
                amount=Decimal("999999999999.99"),
                stage="NEGOTIATION",
                forecast_category="COMMIT",
                expected_close_date=date(2026, 4, 1),
            ),
            _deal_row(
                organization.id,
                amount=Decimal("333.33"),
                probability=33,
                forecast_category="BEST_CASE",
                expected_close_date=date(2026, 4, 30),
            ),
            _deal_row(
                organization.id,
                name="legacy",
                amount=Decimal("0.05"),
                expected_close_date=date(2026, 3, 20),
            ),
            _deal_row(
                organization.id,
                amount=Decimal("7.00"),
                forecast_category="COMMIT",
                expected_close_date=date(2026, 3, 14),
            ),
            _deal_row(
                organization.id,
                amount=Decimal("11.00"),
                forecast_category="BEST_CASE",
                expected_close_date=date(2026, 7, 1),
            ),
            _deal_row(
                organization.id,
                amount=Decimal("200.00"),
                stage="CLOSED_WON",
                closed_at=datetime(2026, 3, 2, tzinfo=UTC),
                stage_entered_at=datetime(2026, 3, 2, tzinfo=UTC),
            ),
            _deal_row(
                organization.id,
                amount=Decimal("5000.00"),
                stage="CLOSED_LOST",
                lost_reason="No budget",
                closed_at=now,
            ),
            _deal_row(
                organization.id,
                amount=Decimal("9.00"),
                currency="USD",
                forecast_category="COMMIT",
                expected_close_date=date(2026, 4, 1),
            ),
            _deal_row(
                other.id,
                amount=Decimal("123.00"),
                forecast_category="COMMIT",
                expected_close_date=date(2026, 4, 1),
            ),
        ]
    )
    pg_session.commit()
    # Rows from before migration 036 and stale categories left on closed deals by the
    # previous release: an open NULL reads as PIPELINE, a closed deal is never categorised.
    pg_session.execute(text("UPDATE deals SET forecast_category = NULL WHERE name = 'legacy'"))
    pg_session.execute(
        text("UPDATE deals SET forecast_category = 'COMMIT' WHERE stage LIKE 'CLOSED%'")
    )
    pg_session.commit()

    service = PipelineService(pg_session)
    forecast = service.forecast(
        organization.id, granularity=ForecastGranularity.MONTH, periods=3, now=now
    )

    def categories(totals: Any) -> list[tuple[str, int, Decimal, Decimal]]:
        return [
            (row.category.value, row.count, row.total_amount, row.weighted_amount)
            for row in totals.category_totals
        ]

    zero = Decimal("0.00")
    assert categories(forecast.periods[0].open) == [
        ("PIPELINE", 1, Decimal("0.05"), Decimal("0.01")),
        ("BEST_CASE", 0, zero, zero),
        ("COMMIT", 0, zero, zero),
    ]
    assert categories(forecast.periods[1].open) == [
        ("PIPELINE", 0, zero, zero),
        ("BEST_CASE", 1, Decimal("333.33"), Decimal("110.00")),
        ("COMMIT", 1, Decimal("999999999999.99"), Decimal("749999999999.99")),
    ]
    assert categories(forecast.past_due) == [
        ("PIPELINE", 0, zero, zero),
        ("BEST_CASE", 0, zero, zero),
        ("COMMIT", 1, Decimal("7.00"), Decimal("0.70")),
    ]
    assert categories(forecast.beyond_horizon) == [
        ("PIPELINE", 0, zero, zero),
        ("BEST_CASE", 1, Decimal("11.00"), Decimal("1.10")),
        ("COMMIT", 0, zero, zero),
    ]
    assert forecast.in_horizon_open.weighted_amount == Decimal("750000000110.00")
    assert forecast.won_in_horizon.total_amount == Decimal("200.00")
    assert forecast.commit_scenario_amount == Decimal("1000000000199.99")
    assert forecast.best_case_scenario_amount == Decimal("1000000000533.32")
    # Unchanged weighted forecast: 200.00 + 0.01 + 110.00 + 749999999999.99.
    assert forecast.projected_in_horizon_amount == Decimal("750000000310.00")
    assert forecast.excluded_other_currency_count == 1
    for bucket in (
        forecast.past_due,
        *(p.open for p in forecast.periods),
        forecast.beyond_horizon,
        forecast.in_horizon_open,
        forecast.open_pipeline,
    ):
        assert sum(row.count for row in bucket.category_totals) == bucket.count
        assert sum(row.total_amount for row in bucket.category_totals) == bucket.total_amount
        assert sum(row.weighted_amount for row in bucket.category_totals) == bucket.weighted_amount

    isolated = service.forecast(other.id, granularity=ForecastGranularity.QUARTER, now=now)
    assert isolated.commit_scenario_amount == Decimal("123.00")
    assert isolated.best_case_scenario_amount == Decimal("123.00")


def test_forecast_targets_on_postgres(pg_session: Session) -> None:
    pg_session.execute(text("SET TIME ZONE 'Asia/Kolkata'"))
    organization, owner = _org_with_owner(pg_session)
    other, _ = _org_with_owner(pg_session, name="Other")
    now = datetime(2026, 3, 15, 12, tzinfo=UTC)
    largest = Decimal("999999999999.99")  # Numeric(14, 2) maximum

    def target(org_id: str, month: date, amount: Decimal, owner_id: str | None = None) -> Any:
        return SalesTarget(
            organization_id=org_id,
            owner_user_id=owner_id,
            period_start=month,
            period_end=date(month.year, month.month + 1, 1) - timedelta(days=1),
            amount=amount,
            currency="INR",
        )

    pg_session.add_all(
        [
            # Q1 fully set at the column maximum: the sum exceeds Numeric(14, 2).
            *(target(organization.id, date(2026, m, 1), largest) for m in (1, 2, 3)),
            # Q2: two months, plus an owner target that must not be added.
            target(organization.id, date(2026, 4, 1), Decimal("0.01")),
            target(organization.id, date(2026, 5, 1), Decimal("0.02")),
            target(organization.id, date(2026, 6, 1), Decimal("50.00"), owner.id),
            target(other.id, date(2026, 6, 1), Decimal("1.00")),
            # 23:30 UTC on 31 March is already 1 April in the session time zone; it is
            # March revenue because periods are UTC.
            _deal_row(
                organization.id,
                amount=Decimal("1000.00"),
                stage="CLOSED_WON",
                closed_at=datetime(2026, 3, 31, 23, 30, tzinfo=UTC),
                stage_entered_at=now,
            ),
        ]
    )
    pg_session.commit()

    forecast = PipelineService(pg_session).forecast(
        organization.id, granularity=ForecastGranularity.QUARTER, periods=2, now=now
    )
    q1, q2 = (period.target for period in forecast.periods)
    assert q1.status == "FULL"
    assert q1.amount == Decimal("2999999999999.97")
    won = q1.comparisons[0]
    assert (won.basis, won.amount, won.attainment_percent) == ("WON", Decimal("1000.00"), "0.0")
    assert won.remaining_amount == Decimal("2999999998999.97")
    assert q2.status == "PARTIAL"
    assert q2.amount == Decimal("0.03")
    assert q2.missing_months == [date(2026, 6, 1)]
    assert q2.has_owner_targets is True
    assert q2.comparisons == []
    assert forecast.target_in_horizon.amount == Decimal("3000000000000.00")
    assert forecast.target_in_horizon.status == "PARTIAL"


def test_forecast_category_deals_reconcile_on_postgres(pg_session: Session) -> None:
    organization, owner = _org_with_owner(pg_session)
    other, _ = _org_with_owner(pg_session, name="Other")
    now = datetime(2026, 3, 15, 12, tzinfo=UTC)
    pg_session.add_all(
        [
            _deal_row(
                organization.id,
                name="largest",
                amount=Decimal("999999999999.99"),
                stage="NEGOTIATION",
                forecast_category="COMMIT",
                owner_user_id=owner.id,
                expected_close_date=date(2026, 4, 1),
            ),
            _deal_row(
                organization.id,
                name="override",
                amount=Decimal("333.33"),
                probability=33,
                forecast_category="COMMIT",
                expected_close_date=date(2026, 4, 30),
            ),
            _deal_row(
                organization.id,
                name="legacy",
                amount=Decimal("0.05"),
                expected_close_date=date(2026, 3, 15),
            ),
            _deal_row(
                organization.id,
                name="past due",
                amount=Decimal("7.00"),
                forecast_category="COMMIT",
                expected_close_date=date(2026, 3, 14),
            ),
            _deal_row(
                organization.id,
                name="beyond",
                amount=Decimal("11.00"),
                forecast_category="COMMIT",
                expected_close_date=date(2026, 7, 1),
            ),
            _deal_row(
                organization.id,
                name="won",
                amount=Decimal("200.00"),
                stage="CLOSED_WON",
                closed_at=datetime(2026, 3, 2, tzinfo=UTC),
            ),
            _deal_row(
                organization.id,
                name="lost",
                amount=Decimal("5000.00"),
                stage="CLOSED_LOST",
                lost_reason="No budget",
                closed_at=now,
            ),
            _deal_row(
                organization.id,
                name="usd",
                amount=Decimal("9.00"),
                currency="USD",
                forecast_category="COMMIT",
                expected_close_date=date(2026, 4, 1),
            ),
            _deal_row(
                other.id,
                name="other org",
                amount=Decimal("123.00"),
                forecast_category="COMMIT",
                expected_close_date=date(2026, 4, 1),
            ),
        ]
    )
    pg_session.commit()
    # Pre-036 rows and stale categories on closed deals, as in the forecast test above.
    pg_session.execute(text("UPDATE deals SET forecast_category = NULL WHERE name = 'legacy'"))
    pg_session.execute(
        text("UPDATE deals SET forecast_category = 'COMMIT' WHERE stage LIKE 'CLOSED%'")
    )
    pg_session.commit()

    service = PipelineService(pg_session)
    month = ForecastGranularity.MONTH
    forecast = service.forecast(organization.id, granularity=month, periods=3, now=now)

    def drill(category: str, organization_id: str = organization.id, **kwargs: Any) -> Any:
        return service.forecast_deals(
            organization_id,
            category=ForecastCategory(category),
            granularity=month,
            periods=3,
            limit=100,
            offset=0,
            now=now,
            **kwargs,
        )

    for category in ("PIPELINE", "BEST_CASE", "COMMIT"):
        for period in forecast.periods:
            page = drill(category, period_start=period.period_start)
            expected = next(
                row for row in period.open.category_totals if row.category.value == category
            )
            assert (page.totals.count, page.totals.total_amount, page.totals.weighted_amount) == (
                expected.count,
                expected.total_amount,
                expected.weighted_amount,
            )
            assert sum(item.amount for item in page.items) == page.totals.total_amount
            assert sum(item.weighted_amount for item in page.items) == page.totals.weighted_amount

    commit = drill("COMMIT")
    assert [item.name for item in commit.items] == ["largest", "override"]
    largest, override = commit.items
    assert largest.amount == Decimal("999999999999.99")
    assert largest.weighted_amount == Decimal("749999999999.99")
    assert (largest.owner_user_id, largest.owner_name) == (owner.id, "Acme Owner")
    assert override.weighted_amount == Decimal("110.00")
    assert override.owner_name is None
    assert commit.totals.total_amount == Decimal("1000000000333.32")
    assert forecast.commit_scenario_amount == (
        forecast.won_in_horizon.total_amount + commit.totals.total_amount
    )
    pipeline = drill("PIPELINE")
    assert [(item.name, item.forecast_category.value) for item in pipeline.items] == [
        ("legacy", "PIPELINE")
    ]
    assert drill("BEST_CASE").items == []

    isolated = drill("COMMIT", organization_id=other.id)
    assert [item.name for item in isolated.items] == ["other org"]
    assert isolated.totals.total_amount == Decimal("123.00")


def test_won_amount_correction_and_probability_history_on_postgres(pg_engine: Any) -> None:
    session = sessionmaker(bind=pg_engine, expire_on_commit=False)()
    try:
        organization, owner = _org_with_owner(session)
        service = DealService(session)
        deal = service.create(
            organization,
            role=MembershipRole.OWNER,
            user_id=owner.id,
            payload=DealCreate(
                name="Audited",
                amount=Decimal("100.00"),
                probability=20,
                expected_close_date=date(2026, 12, 1),
            ),
        )
        deal = service.update(
            organization.id,
            deal.id,
            role=MembershipRole.OWNER,
            user_id=owner.id,
            payload=DealUpdate(expected_revision=1, probability=30),
        )
        deal = service.change_stage(
            organization.id,
            deal.id,
            role=MembershipRole.OWNER,
            user_id=owner.id,
            payload=DealStageChangeRequest(stage=DealStage.CLOSED_WON, expected_revision=2),
        )
        deal = service.correct_won_amount(
            organization.id,
            deal.id,
            role=MembershipRole.OWNER,
            user_id=owner.id,
            payload=DealAmountCorrectionRequest(
                expected_revision=3, amount=Decimal("95.50"), reason="Discount applied"
            ),
        )
        assert deal.amount == Decimal("95.50")
        history = service.history(organization.id, deal.id, limit=10, offset=0).items
        assert [
            (e.changes, e.previous_probability, e.new_probability, e.is_correction) for e in history
        ] == [
            (["CREATED"], None, 20, False),
            (["PROBABILITY"], 20, 30, False),
            (["STAGE", "PROBABILITY", "FORECAST_CATEGORY"], 30, None, False),
            (["AMOUNT"], None, None, True),
        ]
        assert history[-1].change_reason == "Discount applied"
    finally:
        session.close()


def test_only_managers_move_won_deals_on_postgres(pg_engine: Any) -> None:
    session = sessionmaker(bind=pg_engine, expire_on_commit=False)()
    try:
        organization, owner = _org_with_owner(session)
        service = DealService(session)
        deal = service.create(
            organization,
            role=MembershipRole.OWNER,
            user_id=owner.id,
            payload=DealCreate(
                name="Won",
                amount=Decimal("10.00"),
                stage=DealStage.CLOSED_WON,
                expected_close_date=date(2026, 12, 1),
            ),
        )
        reopen = DealStageChangeRequest(stage=DealStage.PROPOSAL, expected_revision=1)
        with pytest.raises(ForbiddenError):
            service.change_stage(
                organization.id,
                deal.id,
                role=MembershipRole.MEMBER,
                user_id=owner.id,
                payload=reopen,
            )
        session.expire_all()
        stored = session.get(Deal, deal.id)
        assert stored is not None
        assert (stored.stage, stored.revision) == ("CLOSED_WON", 1)
        reopened = service.change_stage(
            organization.id, deal.id, role=MembershipRole.ADMIN, user_id=owner.id, payload=reopen
        )
        assert (reopened.stage, reopened.closed_at) == ("PROPOSAL", None)
        history = service.history(organization.id, deal.id, limit=10, offset=0).items
        assert [(e.previous_stage, e.new_stage) for e in history] == [
            (None, DealStage.CLOSED_WON),
            (DealStage.CLOSED_WON, DealStage.PROPOSAL),
        ]
    finally:
        session.close()

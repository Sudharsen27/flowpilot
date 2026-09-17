from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session

from app.models.lead import Lead, LeadSalesAgentAutoStartStatus, LeadSource
from app.repositories.lead_repository import LeadRepository
from tests.test_leads import _auth

EARLIER = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
LATER = EARLIER + timedelta(minutes=5)


def _org_id(client: TestClient) -> str:
    return str(_auth(client)["organization"]["id"])


def _seed_lead(
    db: Session,
    organization_id: str,
    *,
    source: LeadSource = LeadSource.WEBSITE,
    auto_start: LeadSalesAgentAutoStartStatus | None = LeadSalesAgentAutoStartStatus.PENDING,
    created_at: datetime | None = None,
    lead_id: str | None = None,
    name: str = "Ada Prospect",
) -> Lead:
    lead = Lead(
        id=lead_id or str(uuid4()),
        organization_id=organization_id,
        name=name,
        source=source,
        sales_agent_auto_start_status=auto_start,
        created_at=created_at or datetime.now(UTC),
    )
    db.add(lead)
    db.commit()
    db.refresh(lead)
    return lead


def test_claim_sql_uses_for_update_skip_locked(db: Session) -> None:
    compiled = str(
        LeadRepository(db)
        .pending_auto_start_claim_statement(limit=5)
        .compile(dialect=postgresql.dialect())
    )
    assert "FOR UPDATE" in compiled
    assert "SKIP LOCKED" in compiled


def test_pending_website_leads_are_discovered(client: TestClient, db: Session) -> None:
    organization_id = _org_id(client)
    pending = _seed_lead(db, organization_id)
    claimed = _seed_lead(
        db,
        organization_id,
        auto_start=LeadSalesAgentAutoStartStatus.CLAIMED,
        name="Claimed",
    )
    started = _seed_lead(
        db,
        organization_id,
        auto_start=LeadSalesAgentAutoStartStatus.STARTED,
        name="Started",
    )
    skipped = _seed_lead(
        db,
        organization_id,
        auto_start=LeadSalesAgentAutoStartStatus.SKIPPED,
        name="Skipped",
    )
    failed = _seed_lead(
        db,
        organization_id,
        auto_start=LeadSalesAgentAutoStartStatus.FAILED,
        name="Failed",
    )
    unset = _seed_lead(db, organization_id, auto_start=None, name="Unset")
    manual = _seed_lead(
        db,
        organization_id,
        source=LeadSource.MANUAL,
        name="Manual pending",
    )
    rows = LeadRepository(db).list_pending_auto_start(limit=20)
    assert [(row.organization_id, row.id) for row in rows] == [
        (organization_id, pending.id)
    ]
    assert claimed.id not in {row.id for row in rows}
    assert {started.id, skipped.id, failed.id, unset.id, manual.id}.isdisjoint(
        {row.id for row in rows}
    )


def test_pending_auto_start_order_and_limit(client: TestClient, db: Session) -> None:
    organization_id = _org_id(client)
    later_low = _seed_lead(
        db,
        organization_id,
        created_at=LATER,
        lead_id="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
        name="Later low id",
    )
    earlier_high = _seed_lead(
        db,
        organization_id,
        created_at=EARLIER,
        lead_id="ffffffff-ffff-4fff-8fff-ffffffffffff",
        name="Earlier high id",
    )
    earlier_low = _seed_lead(
        db,
        organization_id,
        created_at=EARLIER,
        lead_id="00000000-0000-4000-8000-000000000000",
        name="Earlier low id",
    )
    repository = LeadRepository(db)
    ordered = repository.list_pending_auto_start(limit=20)
    assert [row.id for row in ordered] == [
        earlier_low.id,
        earlier_high.id,
        later_low.id,
    ]
    limited = repository.list_pending_auto_start(limit=2)
    assert [row.id for row in limited] == [earlier_low.id, earlier_high.id]


def test_cas_auto_start_status_transitions_and_misses(
    client: TestClient, db: Session
) -> None:
    first = _auth(client)
    other = _auth(client, email="other@example.com", organization_name="Other Co")
    organization_id = first["organization"]["id"]
    other_org_id = other["organization"]["id"]
    lead = _seed_lead(db, organization_id)
    repository = LeadRepository(db)

    assert (
        repository.cas_auto_start_status(
            organization_id,
            lead.id,
            LeadSalesAgentAutoStartStatus.CLAIMED,
            LeadSalesAgentAutoStartStatus.STARTED,
        )
        == 0
    )
    db.refresh(lead)
    assert lead.sales_agent_auto_start_status == LeadSalesAgentAutoStartStatus.PENDING

    assert (
        repository.cas_auto_start_status(
            other_org_id,
            lead.id,
            LeadSalesAgentAutoStartStatus.PENDING,
            LeadSalesAgentAutoStartStatus.CLAIMED,
        )
        == 0
    )
    db.refresh(lead)
    assert lead.organization_id == organization_id
    assert lead.sales_agent_auto_start_status == LeadSalesAgentAutoStartStatus.PENDING

    assert (
        repository.cas_auto_start_status(
            organization_id,
            lead.id,
            LeadSalesAgentAutoStartStatus.PENDING,
            LeadSalesAgentAutoStartStatus.CLAIMED,
        )
        == 1
    )
    db.refresh(lead)
    assert lead.sales_agent_auto_start_status == LeadSalesAgentAutoStartStatus.CLAIMED

    for to_status in (
        LeadSalesAgentAutoStartStatus.STARTED,
        LeadSalesAgentAutoStartStatus.SKIPPED,
        LeadSalesAgentAutoStartStatus.FAILED,
    ):
        claimed = _seed_lead(db, organization_id, name=f"to {to_status}")
        assert (
            repository.cas_auto_start_status(
                organization_id,
                claimed.id,
                LeadSalesAgentAutoStartStatus.PENDING,
                LeadSalesAgentAutoStartStatus.CLAIMED,
            )
            == 1
        )
        assert (
            repository.cas_auto_start_status(
                organization_id,
                claimed.id,
                LeadSalesAgentAutoStartStatus.CLAIMED,
                to_status,
            )
            == 1
        )
        db.refresh(claimed)
        assert claimed.sales_agent_auto_start_status == to_status
        assert (
            repository.cas_auto_start_status(
                organization_id,
                claimed.id,
                LeadSalesAgentAutoStartStatus.CLAIMED,
                LeadSalesAgentAutoStartStatus.STARTED,
            )
            == 0
        )


def test_sqlite_skip_locked_flag_still_lists_pending(
    client: TestClient, db: Session
) -> None:
    organization_id = _org_id(client)
    lead = _seed_lead(db, organization_id)
    rows = LeadRepository(db).list_pending_auto_start(
        limit=10, for_update_skip_locked=True
    )
    assert [row.id for row in rows] == [lead.id]

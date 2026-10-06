from datetime import UTC, datetime

from sqlalchemy import Select, func, or_, select, update
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from app.models.activity_event import ActivityEvent
from app.models.lead import Lead, LeadSalesAgentAutoStartStatus, LeadSource, LeadStatus

LEAD_LIST_MAX_LIMIT = 50
LEAD_LIST_DEFAULT_LIMIT = 20


class LeadRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, lead: Lead) -> Lead:
        self.session.add(lead)
        return lead

    def get_by_id(self, organization_id: str, lead_id: str) -> Lead | None:
        return self.session.scalar(
            select(Lead).where(
                Lead.organization_id == organization_id,
                Lead.id == lead_id,
            )
        )

    def list_by_email(self, organization_id: str, email: str) -> list[Lead]:
        normalized = email.strip().casefold()
        if not normalized:
            return []
        return list(
            self.session.scalars(
                select(Lead)
                .where(
                    Lead.organization_id == organization_id,
                    Lead.email.is_not(None),
                    func.lower(Lead.email) == normalized,
                )
                .order_by(Lead.created_at.asc(), Lead.id.asc())
            )
        )

    def list_for_organization(
        self,
        organization_id: str,
        *,
        status: LeadStatus | None = None,
        source: LeadSource | None = None,
        search: str | None = None,
        limit: int,
        offset: int,
    ) -> tuple[list[Lead], int]:
        filters = [Lead.organization_id == organization_id]
        if status is not None:
            filters.append(Lead.status == status)
        if source is not None:
            filters.append(Lead.source == source)
        if search:
            pattern = f"%{search}%"
            filters.append(
                or_(
                    Lead.name.ilike(pattern),
                    Lead.email.ilike(pattern),
                    Lead.phone.ilike(pattern),
                    Lead.company.ilike(pattern),
                )
            )
        total = self.session.scalar(
            select(func.count()).select_from(Lead).where(*filters)
        )
        items = list(
            self.session.scalars(
                select(Lead)
                .where(*filters)
                .order_by(Lead.created_at.desc(), Lead.id.desc())
                .limit(limit)
                .offset(offset)
            )
        )
        return items, int(total or 0)

    def status_counts(self, organization_id: str) -> dict[str, int]:
        rows = self.session.execute(
            select(Lead.status, func.count())
            .where(Lead.organization_id == organization_id)
            .group_by(Lead.status)
        ).all()
        counts = {status.value: 0 for status in LeadStatus}
        for status, count in rows:
            counts[str(status)] = int(count)
        return counts

    def pending_auto_start_claim_statement(self, limit: int) -> Select[Lead]:
        """Claim statement for PENDING website leads across all organizations.

        Always carries FOR UPDATE SKIP LOCKED. Only PostgreSQL honours it;
        SQLite ignores the clause, so the locking guarantee exists in
        PostgreSQL only. Rows include organization_id and id for tenant-safe
        worker claiming; organization is never taken from client input.
        """
        return (
            select(Lead)
            .where(
                Lead.sales_agent_auto_start_status
                == LeadSalesAgentAutoStartStatus.PENDING,
                Lead.source == LeadSource.WEBSITE,
            )
            .order_by(Lead.created_at.asc(), Lead.id.asc())
            .limit(limit)
            .with_for_update(skip_locked=True)
        )

    def list_pending_auto_start(
        self,
        *,
        limit: int,
        for_update_skip_locked: bool = False,
    ) -> list[Lead]:
        bind = self.session.get_bind()
        is_postgres = bind is not None and bind.dialect.name == "postgresql"
        if for_update_skip_locked and is_postgres:
            return list(
                self.session.scalars(self.pending_auto_start_claim_statement(limit))
            )
        stmt = (
            select(Lead)
            .where(
                Lead.sales_agent_auto_start_status
                == LeadSalesAgentAutoStartStatus.PENDING,
                Lead.source == LeadSource.WEBSITE,
            )
            .order_by(Lead.created_at.asc(), Lead.id.asc())
            .limit(limit)
        )
        return list(self.session.scalars(stmt))

    def cas_auto_start_status(
        self,
        organization_id: str,
        lead_id: str,
        from_status: LeadSalesAgentAutoStartStatus,
        to_status: LeadSalesAgentAutoStartStatus,
    ) -> int:
        self._expire_leads()
        self.session.flush()
        result = self.session.execute(
            update(Lead)
            .where(
                Lead.organization_id == organization_id,
                Lead.id == lead_id,
                Lead.sales_agent_auto_start_status == from_status,
            )
            .values(sales_agent_auto_start_status=to_status)
        )
        self.session.commit()
        return int(getattr(result, "rowcount", 0) or 0)

    def mark_human_attention_required(self, organization_id: str, lead_id: str) -> bool:
        self._expire_leads()
        self.session.flush()
        result = self.session.execute(
            update(Lead)
            .where(
                Lead.organization_id == organization_id,
                Lead.id == lead_id,
                Lead.human_attention_required.is_(False),
            )
            .values(human_attention_required=True)
        )
        self._expire_leads()
        return int(getattr(result, "rowcount", 0) or 0) == 1

    def latest_human_attention_escalation_event_id(
        self,
        organization_id: str,
        lead_id: str,
        *,
        dedupe_prefix: str,
    ) -> str | None:
        return self.session.scalar(
            select(ActivityEvent.id)
            .where(*self._escalation_event_filters(organization_id, lead_id, dedupe_prefix))
            .order_by(ActivityEvent.occurred_at.desc(), ActivityEvent.id.desc())
            .limit(1)
        )

    def clear_human_attention_required(
        self,
        organization_id: str,
        lead_id: str,
        *,
        expected_updated_at: datetime,
        expected_escalation_event_id: str | None,
        escalation_dedupe_prefix: str,
    ) -> bool:
        """Clear attention only for the episode observed by this request.

        The flag, lead timestamp, and latest escalation event must all still match.
        A newer attention episode fails the predicate and is left in place. The
        identity map is expired so a stale Lead object cannot flush the old flag.
        """
        self._expire_leads()
        self.session.flush()
        latest_escalation_event_id = (
            select(ActivityEvent.id)
            .where(
                *self._escalation_event_filters(
                    organization_id,
                    lead_id,
                    escalation_dedupe_prefix,
                )
            )
            .order_by(ActivityEvent.occurred_at.desc(), ActivityEvent.id.desc())
            .limit(1)
            .scalar_subquery()
        )
        episode_matches = (
            latest_escalation_event_id.is_(None)
            if expected_escalation_event_id is None
            else latest_escalation_event_id == expected_escalation_event_id
        )
        result = self.session.execute(
            update(Lead)
            .where(
                Lead.organization_id == organization_id,
                Lead.id == lead_id,
                Lead.human_attention_required.is_(True),
                Lead.updated_at == expected_updated_at,
                episode_matches,
            )
            .values(
                human_attention_required=False,
                updated_at=datetime.now(UTC),
            )
            .execution_options(synchronize_session=False)
        )
        self._expire_leads()
        return int(getattr(result, "rowcount", 0) or 0) == 1

    def _escalation_event_filters(
        self,
        organization_id: str,
        lead_id: str,
        dedupe_prefix: str,
    ) -> list[ColumnElement[bool]]:
        return [
            ActivityEvent.organization_id == organization_id,
            ActivityEvent.lead_id == lead_id,
            ActivityEvent.dedupe_key.startswith(dedupe_prefix),
        ]

    def _expire_leads(self) -> None:
        for obj in list(self.session.identity_map.values()):
            if isinstance(obj, Lead):
                self.session.expire(obj)

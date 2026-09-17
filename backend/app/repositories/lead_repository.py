from sqlalchemy import Select, func, or_, select, update
from sqlalchemy.orm import Session

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

    def pending_auto_start_claim_statement(self, limit: int) -> Select[tuple[Lead]]:
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

    def _expire_leads(self) -> None:
        for obj in list(self.session.identity_map.values()):
            if isinstance(obj, Lead):
                self.session.expire(obj)

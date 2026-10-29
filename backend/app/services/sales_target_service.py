from datetime import UTC, date, datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, ForbiddenError, UnprocessableError
from app.models.membership import MembershipRole
from app.models.organization import Organization
from app.models.sales_target import SalesTarget
from app.repositories.membership_repository import MembershipRepository
from app.repositories.sales_target_repository import SalesTargetRepository
from app.schemas.sales_targets import SalesTargetListResponse, SalesTargetPublic, SalesTargetUpsert
from app.services.deal_service import as_utc

MANAGER_ROLES = frozenset({MembershipRole.OWNER, MembershipRole.ADMIN})


class SalesTargetService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.targets = SalesTargetRepository(session)

    def list(
        self,
        organization_id: str,
        *,
        owner_user_id: str | None,
        organization_only: bool,
        period_from: date | None,
        period_to: date | None,
        limit: int,
        offset: int,
    ) -> SalesTargetListResponse:
        if period_from and period_to and period_from > period_to:
            raise UnprocessableError("period_from must be on or before period_to")
        rows, total = self.targets.list_for_organization(
            organization_id,
            owner_user_id=owner_user_id,
            organization_only=organization_only,
            period_from=period_from,
            period_to=period_to,
            limit=limit,
            offset=offset,
        )
        return SalesTargetListResponse(
            items=[to_target_public(row) for row in rows],
            limit=limit,
            offset=offset,
            total=total,
        )

    def upsert(
        self,
        organization: Organization,
        *,
        role: str,
        user_id: str,
        payload: SalesTargetUpsert,
    ) -> tuple[SalesTarget, bool]:
        """Create or replace one month's target. Returns the target and whether it is new."""
        if role not in MANAGER_ROLES:
            raise ForbiddenError("Only owners and admins can manage sales targets")
        currency = organization.default_currency
        if payload.currency is not None and payload.currency != currency:
            raise UnprocessableError(
                f"This organization records amounts in {currency}; "
                "currency conversion is not supported"
            )
        if payload.owner_user_id is not None:
            membership = MembershipRepository(self.session).get_for_user_in_organization(
                organization.id, payload.owner_user_id
            )
            if membership is None:
                raise UnprocessableError("Target owner must be a member of this organization")
        if payload.period_end is None:  # set by SalesTargetUpsert validation
            raise UnprocessableError("period_end could not be derived")

        for attempt in range(2):
            now = datetime.now(UTC)
            existing = self.targets.get_for_period(
                organization.id, payload.owner_user_id, payload.period_start
            )
            created = existing is None
            target = existing or self.targets.add(
                SalesTarget(
                    organization_id=organization.id,
                    owner_user_id=payload.owner_user_id,
                    period_start=payload.period_start,
                    period_end=payload.period_end,
                    created_by_user_id=user_id,
                    created_at=now,
                    amount=payload.amount,
                    currency=currency,
                )
            )
            target.amount = payload.amount
            target.currency = currency
            target.updated_by_user_id = user_id
            target.updated_at = now
            try:
                self.session.commit()
            except IntegrityError as exc:
                # A concurrent request created the same month first; update that row instead.
                self.session.rollback()
                if attempt == 0:
                    continue
                raise ConflictError("This sales target was changed concurrently") from exc
            refreshed = self.targets.get_for_period(
                organization.id, payload.owner_user_id, payload.period_start
            )
            if refreshed is None:
                raise ConflictError("This sales target was changed concurrently")
            return refreshed, created
        raise ConflictError("This sales target was changed concurrently")


def to_target_public(row: SalesTarget) -> SalesTargetPublic:
    return SalesTargetPublic(
        id=row.id,
        owner_user_id=row.owner_user_id,
        owner_name=row.owner.name if row.owner else None,
        period_start=row.period_start,
        period_end=row.period_end,
        amount=row.amount,
        currency=row.currency,
        created_by_user_id=row.created_by_user_id,
        updated_by_user_id=row.updated_by_user_id,
        created_at=as_utc(row.created_at),
        updated_at=as_utc(row.updated_at),
    )

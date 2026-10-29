from datetime import UTC, date, datetime

from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError, UnprocessableError
from app.models.activity_event import ActivityActorType, ActivityEntityType, ActivityEventType
from app.models.deal import (
    CLOSED_DEAL_STAGES,
    DEAL_STAGE_DEFAULT_PROBABILITY,
    Deal,
    DealStage,
    DealStageEvent,
    effective_probability,
)
from app.models.lead import LeadStatus
from app.models.membership import MembershipRole
from app.models.organization import Organization
from app.repositories.deal_repository import DealRepository
from app.repositories.lead_repository import LeadRepository
from app.repositories.membership_repository import MembershipRepository
from app.schemas.deals import (
    DealCreate,
    DealHistoryChange,
    DealHistoryEvent,
    DealHistoryResponse,
    DealListResponse,
    DealPublic,
    DealStageChangeRequest,
    DealUpdate,
)
from app.services.activity_service import ActivityService

MANAGER_ROLES = frozenset({MembershipRole.OWNER, MembershipRole.ADMIN})
STALE_DEAL_DETAIL = "This deal changed. Refresh and review the latest version."


class DealService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.deals = DealRepository(session)

    def create(
        self,
        organization: Organization,
        *,
        role: str,
        user_id: str,
        payload: DealCreate,
    ) -> Deal:
        currency = _organization_currency(organization, payload.currency)
        stage = DealStage(payload.stage)
        _validate_stage_fields(stage, payload.probability, payload.lost_reason)
        owner_user_id = (
            payload.owner_user_id if "owner_user_id" in payload.model_fields_set else user_id
        )
        if owner_user_id is not None and owner_user_id != user_id:
            _require_manager(role, "Only owners and admins can assign deals to other members")
        self._require_member(organization.id, owner_user_id)

        now = datetime.now(UTC)
        try:
            if payload.lead_id is not None:
                self._convert_lead(organization.id, payload.lead_id, user_id)
            deal = self.deals.add(
                Deal(
                    organization_id=organization.id,
                    lead_id=payload.lead_id,
                    name=payload.name,
                    description=payload.description,
                    amount=payload.amount,
                    currency=currency,
                    stage=stage,
                    probability=payload.probability,
                    expected_close_date=payload.expected_close_date,
                    closed_at=now if stage in CLOSED_DEAL_STAGES else None,
                    owner_user_id=owner_user_id,
                    lost_reason=payload.lost_reason,
                    revision=1,
                    stage_entered_at=now,
                    created_at=now,
                    updated_at=now,
                )
            )
            self.session.flush()
            self._record_event(
                deal,
                previous_stage=None,
                previous_amount=None,
                previous_expected_close_date=None,
                changed_by_user_id=user_id,
                change_reason=None,
                created_at=now,
            )
            self.session.commit()
        except Exception:
            # Deal, history and lead conversion are one unit: nothing persists on failure.
            self.session.rollback()
            raise
        return self.get(organization.id, deal.id)

    def get(self, organization_id: str, deal_id: str) -> Deal:
        deal = self.deals.get_by_id(organization_id, deal_id)
        if deal is None:
            raise NotFoundError("Deal not found")
        return deal

    def list(
        self,
        organization_id: str,
        *,
        stage: DealStage | None,
        owner_user_id: str | None,
        close_date_from: date | None,
        close_date_to: date | None,
        search: str | None,
        limit: int,
        offset: int,
    ) -> DealListResponse:
        if close_date_from and close_date_to and close_date_from > close_date_to:
            raise UnprocessableError("close_date_from must be on or before close_date_to")
        normalized_search = " ".join(search.split()).casefold() if search else None
        rows, total = self.deals.list_for_organization(
            organization_id,
            stage=stage,
            owner_user_id=owner_user_id,
            close_date_from=close_date_from,
            close_date_to=close_date_to,
            search=normalized_search,
            limit=limit,
            offset=offset,
        )
        return DealListResponse(
            items=[to_deal_public(row) for row in rows],
            limit=limit,
            offset=offset,
            total=total,
        )

    def update(
        self,
        organization_id: str,
        deal_id: str,
        *,
        role: str,
        user_id: str,
        payload: DealUpdate,
    ) -> Deal:
        try:
            deal = self._lock(organization_id, deal_id, payload.expected_revision)
            fields = payload.model_fields_set
            stage = DealStage(deal.stage)
            previous_amount = deal.amount
            previous_close_date = deal.expected_close_date
            changed = False

            for field in ("name", "amount", "expected_close_date"):
                if field in fields and getattr(payload, field) is None:
                    raise UnprocessableError(f"{field} cannot be cleared")
            if payload.name is not None and payload.name != deal.name:
                deal.name = payload.name
                changed = True
            if "description" in fields and payload.description != deal.description:
                deal.description = payload.description
                changed = True
            if payload.amount is not None and payload.amount != deal.amount:
                deal.amount = payload.amount
                changed = True
            if (
                payload.expected_close_date is not None
                and payload.expected_close_date != deal.expected_close_date
            ):
                deal.expected_close_date = payload.expected_close_date
                changed = True
            if "probability" in fields and payload.probability != deal.probability:
                if payload.probability is not None and stage in CLOSED_DEAL_STAGES:
                    raise UnprocessableError("Closed deals use a fixed probability")
                deal.probability = payload.probability
                changed = True
            if "owner_user_id" in fields and payload.owner_user_id != deal.owner_user_id:
                _require_manager(role, "Only owners and admins can reassign deal owners")
                self._require_member(organization_id, payload.owner_user_id)
                deal.owner_user_id = payload.owner_user_id
                changed = True
            if "lost_reason" in fields and payload.lost_reason != deal.lost_reason:
                if stage != DealStage.CLOSED_LOST:
                    raise UnprocessableError("Only lost deals have a lost reason")
                if payload.lost_reason is None:
                    raise UnprocessableError("Lost deals require a lost reason")
                deal.lost_reason = payload.lost_reason
                changed = True

            if not changed:
                self.session.rollback()
                return self.get(organization_id, deal_id)

            now = datetime.now(UTC)
            deal.revision += 1
            deal.updated_at = now
            if deal.amount != previous_amount or deal.expected_close_date != previous_close_date:
                self._record_event(
                    deal,
                    previous_stage=stage,
                    previous_amount=previous_amount,
                    previous_expected_close_date=previous_close_date,
                    changed_by_user_id=user_id,
                    change_reason=payload.change_reason,
                    created_at=now,
                )
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise
        return self.get(organization_id, deal_id)

    def change_stage(
        self,
        organization_id: str,
        deal_id: str,
        *,
        user_id: str,
        payload: DealStageChangeRequest,
    ) -> Deal:
        new_stage = DealStage(payload.stage)
        try:
            deal = self._lock(organization_id, deal_id, payload.expected_revision)
            previous_stage = DealStage(deal.stage)
            if new_stage == previous_stage:
                if payload.probability is not None or payload.lost_reason is not None:
                    raise UnprocessableError(
                        "The deal is already in this stage; use PATCH to change other fields"
                    )
                self.session.rollback()
                return self.get(organization_id, deal_id)
            _validate_stage_fields(new_stage, payload.probability, payload.lost_reason)

            now = datetime.now(UTC)
            deal.stage = new_stage
            deal.stage_entered_at = now
            deal.closed_at = now if new_stage in CLOSED_DEAL_STAGES else None
            # An override belongs to the stage it was set for.
            deal.probability = payload.probability
            deal.lost_reason = payload.lost_reason if new_stage == DealStage.CLOSED_LOST else None
            deal.revision += 1
            deal.updated_at = now
            self._record_event(
                deal,
                previous_stage=previous_stage,
                previous_amount=deal.amount,
                previous_expected_close_date=deal.expected_close_date,
                changed_by_user_id=user_id,
                change_reason=payload.change_reason,
                created_at=now,
            )
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise
        return self.get(organization_id, deal_id)

    def history(
        self, organization_id: str, deal_id: str, *, limit: int, offset: int
    ) -> DealHistoryResponse:
        self.get(organization_id, deal_id)
        rows, total = self.deals.list_events(organization_id, deal_id, limit=limit, offset=offset)
        return DealHistoryResponse(
            items=[to_history_event(row) for row in rows],
            limit=limit,
            offset=offset,
            total=total,
        )

    def _lock(self, organization_id: str, deal_id: str, expected_revision: int) -> Deal:
        deal = self.deals.get_by_id(organization_id, deal_id, for_update=True)
        if deal is None:
            raise NotFoundError("Deal not found")
        if deal.revision != expected_revision:
            raise ConflictError(
                STALE_DEAL_DETAIL,
                {"detail": STALE_DEAL_DETAIL, "current_revision": deal.revision},
            )
        return deal

    def _require_member(self, organization_id: str, user_id: str | None) -> None:
        if user_id is None:
            return
        membership = MembershipRepository(self.session).get_for_user_in_organization(
            organization_id, user_id
        )
        if membership is None:
            raise UnprocessableError("Deal owner must be a member of this organization")

    def _convert_lead(self, organization_id: str, lead_id: str, user_id: str) -> None:
        lead = LeadRepository(self.session).get_by_id(organization_id, lead_id)
        if lead is None:
            raise NotFoundError("Lead not found")
        if lead.status == LeadStatus.CONVERTED:
            return
        lead.status = LeadStatus.CONVERTED
        lead.updated_at = datetime.now(UTC)
        # Same convention as LeadService.update so lead history reads the same either way.
        ActivityService(self.session).record(
            organization_id=organization_id,
            event_type=ActivityEventType.HUMAN_ACTION,
            actor_type=ActivityActorType.USER,
            title="Lead status changed",
            summary="A lead CRM status was updated.",
            entity_type=ActivityEntityType.LEAD,
            entity_id=lead.id,
            lead_id=lead.id,
            actor_user_id=user_id,
            status=LeadStatus.CONVERTED,
            dedupe_key=f"lead:{lead.id}:STATUS:{LeadStatus.CONVERTED}",
        )

    def _record_event(
        self,
        deal: Deal,
        *,
        previous_stage: DealStage | None,
        previous_amount: object,
        previous_expected_close_date: date | None,
        changed_by_user_id: str | None,
        change_reason: str | None,
        created_at: datetime,
    ) -> None:
        self.deals.add_event(
            DealStageEvent(
                organization_id=deal.organization_id,
                deal_id=deal.id,
                previous_stage=previous_stage,
                new_stage=deal.stage,
                previous_amount=previous_amount,
                new_amount=deal.amount,
                previous_expected_close_date=previous_expected_close_date,
                new_expected_close_date=deal.expected_close_date,
                changed_by_user_id=changed_by_user_id,
                change_reason=change_reason,
                created_at=created_at,
            )
        )


def as_utc(value: datetime) -> datetime:
    """SQLite returns naive datetimes; every stored timestamp is UTC."""
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def to_deal_public(deal: Deal) -> DealPublic:
    probability = effective_probability(deal.stage, deal.probability)
    uses_override = deal.probability is not None and DealStage(deal.stage) not in CLOSED_DEAL_STAGES
    return DealPublic(
        id=deal.id,
        name=deal.name,
        description=deal.description,
        amount=deal.amount,
        currency=deal.currency,
        stage=DealStage(deal.stage),
        probability=deal.probability,
        effective_probability=probability,
        probability_source="OVERRIDE" if uses_override else "STAGE_DEFAULT",
        expected_close_date=deal.expected_close_date,
        closed_at=as_utc(deal.closed_at) if deal.closed_at else None,
        owner_user_id=deal.owner_user_id,
        owner_name=deal.owner.name if deal.owner else None,
        lead_id=deal.lead_id,
        lead_name=deal.lead.name if deal.lead else None,
        lost_reason=deal.lost_reason,
        revision=deal.revision,
        stage_entered_at=as_utc(deal.stage_entered_at),
        created_at=as_utc(deal.created_at),
        updated_at=as_utc(deal.updated_at),
    )


def to_history_event(row: DealStageEvent) -> DealHistoryEvent:
    changes: list[DealHistoryChange] = []
    if row.previous_stage is None:
        changes.append("CREATED")
    else:
        if row.previous_stage != row.new_stage:
            changes.append("STAGE")
        if row.previous_amount != row.new_amount:
            changes.append("AMOUNT")
        if row.previous_expected_close_date != row.new_expected_close_date:
            changes.append("EXPECTED_CLOSE_DATE")
    return DealHistoryEvent(
        id=row.id,
        deal_id=row.deal_id,
        changes=changes,
        previous_stage=DealStage(row.previous_stage) if row.previous_stage else None,
        new_stage=DealStage(row.new_stage),
        previous_amount=row.previous_amount,
        new_amount=row.new_amount,
        previous_expected_close_date=row.previous_expected_close_date,
        new_expected_close_date=row.new_expected_close_date,
        changed_by_user_id=row.changed_by_user_id,
        changed_by_name=row.changed_by.name if row.changed_by else None,
        change_reason=row.change_reason,
        created_at=as_utc(row.created_at),
    )


def _organization_currency(organization: Organization, requested: str | None) -> str:
    currency = organization.default_currency
    if requested is not None and requested != currency:
        raise UnprocessableError(
            f"This organization records amounts in {currency}; currency conversion is not supported"
        )
    return currency


def _validate_stage_fields(
    stage: DealStage, probability: int | None, lost_reason: str | None
) -> None:
    if probability is not None and stage in CLOSED_DEAL_STAGES:
        raise UnprocessableError(
            f"{stage.value} deals use a fixed probability of "
            f"{DEAL_STAGE_DEFAULT_PROBABILITY[stage]}%"
        )
    if stage == DealStage.CLOSED_LOST and lost_reason is None:
        raise UnprocessableError("Lost deals require a lost reason")
    if stage != DealStage.CLOSED_LOST and lost_reason is not None:
        raise UnprocessableError("Only lost deals have a lost reason")


def _require_manager(role: str, detail: str) -> None:
    if role not in MANAGER_ROLES:
        raise ForbiddenError(detail)

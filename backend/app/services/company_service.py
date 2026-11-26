from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError, UnprocessableError
from app.models.activity_event import ActivityActorType, ActivityEntityType, ActivityEventType
from app.models.company import Company, CompanyLifecycleStatus, CompanySource
from app.models.membership import MembershipRole
from app.repositories.company_repository import CompanyRepository
from app.repositories.membership_repository import MembershipRepository
from app.schemas.company import (
    CompanyCreate,
    CompanyListResponse,
    CompanyPublic,
    CompanyUpdate,
)
from app.services.activity_service import ActivityService

COMPANY_LIST_DEFAULT_LIMIT = 20
COMPANY_LIST_MAX_LIMIT = 100
STALE_COMPANY_DETAIL = "This company changed. Refresh and review the latest version."
ARCHIVED_COMPANY_DETAIL = "Archived companies cannot be edited. Restore the company first."
COMPANY_OWNER_MEMBERSHIP_DETAIL = "Company owner must be a member of this organization"
MEMBER_COMPANY_EDIT_DETAIL = "Members can edit only companies they own"
MEMBER_OWNER_ASSIGNMENT_DETAIL = "Members cannot assign company owners"
COMPANY_MANAGER_REQUIRED_DETAIL = "Only owners and admins can manage company ownership and archive"
_MANAGER_ROLES = frozenset({MembershipRole.OWNER, MembershipRole.ADMIN})


def _membership_role(role: str) -> MembershipRole:
    try:
        return MembershipRole(role)
    except ValueError as exc:
        raise ForbiddenError(COMPANY_MANAGER_REQUIRED_DETAIL) from exc


class CompanyService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.companies = CompanyRepository(session)
        self.memberships = MembershipRepository(session)

    def create(
        self,
        organization_id: str,
        *,
        role: str,
        actor_user_id: str,
        payload: CompanyCreate,
    ) -> Company:
        actor_role = _membership_role(role)
        owner_user_id: str | None
        if actor_role == MembershipRole.MEMBER:
            if "owner_user_id" in payload.model_fields_set:
                raise ForbiddenError(MEMBER_OWNER_ASSIGNMENT_DETAIL)
            owner_user_id = actor_user_id
        elif "owner_user_id" in payload.model_fields_set:
            owner_user_id = payload.owner_user_id
        else:
            owner_user_id = actor_user_id
        self._require_organization_member(organization_id, owner_user_id)

        values = payload.model_dump(exclude={"owner_user_id"})
        company = Company(
            organization_id=organization_id,
            owner_user_id=owner_user_id,
            source=CompanySource.MANUAL,
            **values,
        )
        try:
            self.companies.add(company)
            self.session.flush()
            self._record_lifecycle_activity(company, actor_user_id, "CREATED")
            self.session.commit()
            self.session.refresh(company)
        except Exception:
            self.session.rollback()
            raise
        return company

    def get(self, organization_id: str, company_id: str) -> Company:
        company = self.companies.get_by_id(organization_id, company_id)
        if company is None:
            raise NotFoundError("Company not found")
        return company

    def list(
        self,
        organization_id: str,
        *,
        search: str | None,
        lifecycle_status: CompanyLifecycleStatus | None,
        owner_user_id: str | None,
        include_archived: bool,
        limit: int,
        offset: int,
    ) -> CompanyListResponse:
        normalized_search = " ".join(search.split()).casefold() if search else None
        rows, total = self.companies.list_for_organization(
            organization_id,
            search=normalized_search,
            lifecycle_status=lifecycle_status,
            owner_user_id=owner_user_id,
            include_archived=include_archived,
            limit=limit,
            offset=offset,
        )
        return CompanyListResponse(
            items=[CompanyPublic.model_validate(row) for row in rows],
            limit=limit,
            offset=offset,
            total=total,
        )

    def update(
        self,
        organization_id: str,
        company_id: str,
        *,
        role: str,
        actor_user_id: str,
        payload: CompanyUpdate,
    ) -> Company:
        try:
            company = self._get_for_update(organization_id, company_id)
            actor_role = _membership_role(role)
            fields = payload.model_fields_set - {"expected_revision"}
            if actor_role == MembershipRole.MEMBER:
                if "owner_user_id" in fields:
                    raise ForbiddenError(MEMBER_OWNER_ASSIGNMENT_DETAIL)
                if company.owner_user_id != actor_user_id:
                    raise ForbiddenError(MEMBER_COMPANY_EDIT_DETAIL)
            self._check_revision(company, payload.expected_revision)
            if company.archived_at is not None:
                raise ConflictError(ARCHIVED_COMPANY_DETAIL)

            changed = False
            for field in fields:
                value = getattr(payload, field)
                if field == "name" and value is None:
                    raise UnprocessableError("Company name cannot be cleared")
                if field == "lifecycle_status" and value is None:
                    raise UnprocessableError("Company lifecycle status cannot be cleared")
                if field == "owner_user_id":
                    self._require_organization_member(organization_id, value)
                if getattr(company, field) != value:
                    setattr(company, field, value)
                    changed = True

            if not changed:
                self.session.rollback()
                return self.get(organization_id, company_id)

            company.revision += 1
            company.updated_at = datetime.now(UTC)
            self._record_lifecycle_activity(company, actor_user_id, "UPDATED")
            self.session.commit()
            self.session.refresh(company)
        except Exception:
            self.session.rollback()
            raise
        return company

    def archive(
        self,
        organization_id: str,
        company_id: str,
        *,
        role: str,
        actor_user_id: str,
        expected_revision: int,
    ) -> Company:
        return self._set_archived(
            organization_id,
            company_id,
            role=role,
            actor_user_id=actor_user_id,
            expected_revision=expected_revision,
            archived=True,
        )

    def restore(
        self,
        organization_id: str,
        company_id: str,
        *,
        role: str,
        actor_user_id: str,
        expected_revision: int,
    ) -> Company:
        return self._set_archived(
            organization_id,
            company_id,
            role=role,
            actor_user_id=actor_user_id,
            expected_revision=expected_revision,
            archived=False,
        )

    def _set_archived(
        self,
        organization_id: str,
        company_id: str,
        *,
        role: str,
        actor_user_id: str,
        expected_revision: int,
        archived: bool,
    ) -> Company:
        try:
            company = self._get_for_update(organization_id, company_id)
            actor_role = _membership_role(role)
            if actor_role not in _MANAGER_ROLES:
                raise ForbiddenError(COMPANY_MANAGER_REQUIRED_DETAIL)
            self._check_revision(company, expected_revision)

            is_archived = company.archived_at is not None
            if is_archived == archived:
                self.session.rollback()
                return self.get(organization_id, company_id)

            company.archived_at = datetime.now(UTC) if archived else None
            company.revision += 1
            company.updated_at = datetime.now(UTC)
            self._record_lifecycle_activity(
                company,
                actor_user_id,
                "ARCHIVED" if archived else "RESTORED",
            )
            self.session.commit()
            self.session.refresh(company)
        except Exception:
            self.session.rollback()
            raise
        return company

    def _record_lifecycle_activity(
        self, company: Company, actor_user_id: str, action: str
    ) -> None:
        ActivityService(self.session).record(
            organization_id=company.organization_id,
            event_type=ActivityEventType.HUMAN_ACTION,
            actor_type=ActivityActorType.USER,
            actor_user_id=actor_user_id,
            title=f"Company {action.lower()}",
            summary="A company record was changed.",
            entity_type=ActivityEntityType.COMPANY,
            entity_id=company.id,
            status=action,
            dedupe_key=f"company:{company.id}:{action}:r{company.revision}",
        )

    def _get_for_update(self, organization_id: str, company_id: str) -> Company:
        company = self.companies.get_by_id(organization_id, company_id, for_update=True)
        if company is None:
            raise NotFoundError("Company not found")
        return company

    def _check_revision(self, company: Company, expected_revision: int) -> None:
        if company.revision != expected_revision:
            raise ConflictError(
                STALE_COMPANY_DETAIL,
                {"detail": STALE_COMPANY_DETAIL, "current_revision": company.revision},
            )

    def _require_organization_member(self, organization_id: str, user_id: str | None) -> None:
        if (
            user_id is not None
            and self.memberships.get_for_user_in_organization(organization_id, user_id) is None
        ):
            raise UnprocessableError(COMPANY_OWNER_MEMBERSHIP_DETAIL)

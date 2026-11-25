from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError, UnprocessableError
from app.models.company import Company
from app.models.contact import Contact, ContactSource, ContactStatus
from app.models.lead import Lead
from app.models.membership import Membership, MembershipRole
from app.repositories.company_repository import CompanyRepository
from app.repositories.contact_repository import ContactRepository
from app.repositories.lead_repository import LeadRepository
from app.repositories.membership_repository import MembershipRepository
from app.schemas.contacts import (
    CONTACT_LIST_DEFAULT_LIMIT,
    CONTACT_LIST_MAX_LIMIT,
    LINKED_LEAD_LIST_DEFAULT_LIMIT,
    LINKED_LEAD_LIST_MAX_LIMIT,
    ContactCreate,
    ContactLeadLinkRequest,
    ContactLeadLinkResponse,
    ContactListResponse,
    ContactPublic,
    ContactUpdate,
    LinkedLeadListResponse,
    LinkedLeadSummary,
)

STALE_CONTACT_DETAIL = "This contact changed. Refresh and review the latest version."
ARCHIVED_CONTACT_DETAIL = "Archived contacts cannot be edited. Restore the contact first."
ARCHIVED_COMPANY_DETAIL = "Archived companies cannot be assigned to contacts."
CONTACT_OWNER_MEMBERSHIP_DETAIL = "Contact owner not found"
MEMBER_CONTACT_EDIT_DETAIL = "Members can edit only contacts they own"
MEMBER_OWNER_ASSIGNMENT_DETAIL = "Members cannot assign contact owners"
CONTACT_MANAGER_REQUIRED_DETAIL = (
    "Only owners and admins can manage contact ownership and archive"
)
_MANAGER_ROLES = frozenset({MembershipRole.OWNER, MembershipRole.ADMIN})


def _membership_role(role: str) -> MembershipRole:
    try:
        return MembershipRole(role)
    except ValueError as exc:
        raise ForbiddenError(CONTACT_MANAGER_REQUIRED_DETAIL) from exc


class ContactService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.contacts = ContactRepository(session)
        self.companies = CompanyRepository(session)
        self.leads = LeadRepository(session)
        self.memberships = MembershipRepository(session)

    def create(self, membership: Membership, payload: ContactCreate) -> Contact:
        organization_id = membership.organization_id
        actor_role = _membership_role(membership.role)
        owner_user_id: str | None
        if actor_role == MembershipRole.MEMBER:
            if "owner_user_id" in payload.model_fields_set:
                raise ForbiddenError(MEMBER_OWNER_ASSIGNMENT_DETAIL)
            owner_user_id = membership.user_id
        elif "owner_user_id" in payload.model_fields_set:
            owner_user_id = payload.owner_user_id
        else:
            owner_user_id = membership.user_id

        self._require_organization_member(organization_id, owner_user_id)
        self._require_assignable_company(organization_id, payload.company_id)

        values = payload.model_dump(exclude={"owner_user_id"})
        contact = Contact(
            organization_id=organization_id,
            owner_user_id=owner_user_id,
            source=ContactSource.MANUAL,
            **values,
        )
        try:
            self.contacts.add(contact)
            self.session.commit()
            self.session.refresh(contact)
        except Exception:
            self.session.rollback()
            raise
        return contact

    def list(
        self,
        membership: Membership,
        *,
        search: str | None = None,
        company_id: str | None = None,
        status: ContactStatus | None = None,
        owner_user_id: str | None = None,
        lead_id: str | None = None,
        include_archived: bool = False,
        limit: int = CONTACT_LIST_DEFAULT_LIMIT,
        offset: int = 0,
    ) -> ContactListResponse:
        organization_id = membership.organization_id
        _validate_pagination(limit, offset, CONTACT_LIST_MAX_LIMIT)
        if company_id is not None:
            self._require_company(organization_id, company_id)
        if lead_id is not None:
            self._require_lead(organization_id, lead_id)
        if owner_user_id is not None:
            self._require_organization_member(organization_id, owner_user_id)

        normalized_search = " ".join(search.split()).casefold() if search else None
        rows, total = self.contacts.list_for_organization(
            organization_id,
            search=normalized_search,
            company_id=company_id,
            status=status,
            owner_user_id=owner_user_id,
            lead_id=lead_id,
            include_archived=include_archived,
            limit=limit,
            offset=offset,
        )
        return ContactListResponse(
            items=[ContactPublic.model_validate(row) for row in rows],
            limit=limit,
            offset=offset,
            total=total,
        )

    def get(self, membership: Membership, contact_id: str) -> Contact:
        contact = self.contacts.get_by_id(membership.organization_id, contact_id)
        if contact is None:
            raise NotFoundError("Contact not found")
        return contact

    def update(
        self,
        membership: Membership,
        contact_id: str,
        payload: ContactUpdate,
    ) -> Contact:
        organization_id = membership.organization_id
        try:
            contact = self._get_for_update(organization_id, contact_id)
            actor_role = _membership_role(membership.role)
            fields = payload.model_fields_set - {"expected_revision"}
            self._authorize_edit(contact, actor_role, membership.user_id, fields)
            self._check_revision(contact, payload.expected_revision)

            if "company_id" in fields and payload.company_id != contact.company_id:
                self._require_assignable_company(organization_id, payload.company_id)
            if "owner_user_id" in fields:
                self._require_organization_member(organization_id, payload.owner_user_id)

            if contact.archived_at is not None:
                raise ConflictError(ARCHIVED_CONTACT_DETAIL)

            changed = False
            for field in fields:
                value = getattr(payload, field)
                if getattr(contact, field) != value:
                    setattr(contact, field, value)
                    changed = True

            if not changed:
                self.session.rollback()
                return self.get(membership, contact_id)

            contact.revision += 1
            contact.updated_at = datetime.now(UTC)
            self.session.commit()
            self.session.refresh(contact)
        except Exception:
            self.session.rollback()
            raise
        return contact

    def archive(
        self,
        membership: Membership,
        contact_id: str,
        *,
        expected_revision: int,
    ) -> Contact:
        return self._set_archived(
            membership,
            contact_id,
            expected_revision=expected_revision,
            archived=True,
        )

    def restore(
        self,
        membership: Membership,
        contact_id: str,
        *,
        expected_revision: int,
    ) -> Contact:
        return self._set_archived(
            membership,
            contact_id,
            expected_revision=expected_revision,
            archived=False,
        )

    def list_leads(
        self,
        membership: Membership,
        contact_id: str,
        *,
        limit: int = LINKED_LEAD_LIST_DEFAULT_LIMIT,
        offset: int = 0,
    ) -> LinkedLeadListResponse:
        _validate_pagination(limit, offset, LINKED_LEAD_LIST_MAX_LIMIT)
        self.get(membership, contact_id)
        rows, total = self.contacts.list_leads_for_contact(
            membership.organization_id,
            contact_id,
            limit=limit,
            offset=offset,
        )
        return LinkedLeadListResponse(
            items=[LinkedLeadSummary.model_validate(row) for row in rows],
            limit=limit,
            offset=offset,
            total=total,
        )

    def set_lead_link(
        self,
        membership: Membership,
        contact_id: str,
        payload: ContactLeadLinkRequest,
    ) -> ContactLeadLinkResponse:
        organization_id = membership.organization_id
        try:
            contact = self._get_for_update(organization_id, contact_id)
            actor_role = _membership_role(membership.role)
            self._authorize_edit(contact, actor_role, membership.user_id, set())
            self._check_revision(contact, payload.expected_revision)
            self._require_lead(organization_id, payload.lead_id)

            if contact.archived_at is not None:
                raise ConflictError(ARCHIVED_CONTACT_DETAIL)

            is_linked = self.contacts.is_linked_to_lead(
                organization_id,
                contact_id,
                payload.lead_id,
            )
            if is_linked == payload.linked:
                revision = contact.revision
                self.session.rollback()
                return ContactLeadLinkResponse(
                    contact_id=contact_id,
                    lead_id=payload.lead_id,
                    linked=payload.linked,
                    revision=revision,
                )

            if payload.linked:
                changed = self.contacts.link_to_lead(
                    organization_id,
                    contact_id,
                    payload.lead_id,
                )
            else:
                changed = self.contacts.unlink_from_lead(
                    organization_id,
                    contact_id,
                    payload.lead_id,
                )
            if not changed:
                raise ConflictError(STALE_CONTACT_DETAIL)

            contact.revision += 1
            contact.updated_at = datetime.now(UTC)
            self.session.commit()
            self.session.refresh(contact)
        except Exception:
            self.session.rollback()
            raise

        return ContactLeadLinkResponse(
            contact_id=contact.id,
            lead_id=payload.lead_id,
            linked=payload.linked,
            revision=contact.revision,
        )

    def _set_archived(
        self,
        membership: Membership,
        contact_id: str,
        *,
        expected_revision: int,
        archived: bool,
    ) -> Contact:
        try:
            contact = self._get_for_update(membership.organization_id, contact_id)
            actor_role = _membership_role(membership.role)
            if actor_role not in _MANAGER_ROLES:
                raise ForbiddenError(CONTACT_MANAGER_REQUIRED_DETAIL)
            self._check_revision(contact, expected_revision)

            is_archived = contact.archived_at is not None
            if is_archived == archived:
                self.session.rollback()
                return self.get(membership, contact_id)

            contact.archived_at = datetime.now(UTC) if archived else None
            contact.revision += 1
            contact.updated_at = datetime.now(UTC)
            self.session.commit()
            self.session.refresh(contact)
        except Exception:
            self.session.rollback()
            raise
        return contact

    def _get_for_update(self, organization_id: str, contact_id: str) -> Contact:
        contact = self.contacts.get_by_id(organization_id, contact_id, for_update=True)
        if contact is None:
            raise NotFoundError("Contact not found")
        return contact

    def _check_revision(self, contact: Contact, expected_revision: int) -> None:
        if contact.revision != expected_revision:
            raise ConflictError(
                STALE_CONTACT_DETAIL,
                {"detail": STALE_CONTACT_DETAIL, "current_revision": contact.revision},
            )

    def _authorize_edit(
        self,
        contact: Contact,
        role: MembershipRole,
        actor_user_id: str,
        fields: set[str],
    ) -> None:
        if role == MembershipRole.MEMBER:
            if "owner_user_id" in fields:
                raise ForbiddenError(MEMBER_OWNER_ASSIGNMENT_DETAIL)
            if contact.owner_user_id != actor_user_id:
                raise ForbiddenError(MEMBER_CONTACT_EDIT_DETAIL)

    def _require_assignable_company(self, organization_id: str, company_id: str | None) -> None:
        if company_id is None:
            return
        company = self._require_company(organization_id, company_id)
        if company.archived_at is not None:
            raise ConflictError(ARCHIVED_COMPANY_DETAIL)

    def _require_company(self, organization_id: str, company_id: str) -> Company:
        company = self.companies.get_by_id(organization_id, company_id)
        if company is None:
            raise NotFoundError("Company not found")
        return company

    def _require_lead(self, organization_id: str, lead_id: str) -> Lead:
        lead = self.leads.get_by_id(organization_id, lead_id)
        if lead is None:
            raise NotFoundError("Lead not found")
        return lead

    def _require_organization_member(self, organization_id: str, user_id: str | None) -> None:
        if (
            user_id is not None
            and self.memberships.get_for_user_in_organization(organization_id, user_id) is None
        ):
            raise NotFoundError(CONTACT_OWNER_MEMBERSHIP_DETAIL)


def _validate_pagination(limit: int, offset: int, maximum: int) -> None:
    if limit < 1 or limit > maximum or offset < 0:
        raise UnprocessableError("Invalid pagination parameters")

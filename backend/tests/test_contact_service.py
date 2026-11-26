from datetime import UTC, datetime
from typing import Any, TypedDict
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError, UnprocessableError
from app.models.activity_event import (
    ActivityActorType,
    ActivityEntityType,
    ActivityEvent,
    ActivityEventType,
)
from app.models.company import Company
from app.models.contact import Contact, ContactSource, ContactStatus
from app.models.lead import Lead
from app.models.membership import Membership, MembershipRole
from app.models.organization import Organization
from app.models.user import User
from app.repositories.contact_repository import ContactRepository
from app.schemas.contacts import (
    ContactCreate,
    ContactLeadLinkRequest,
    ContactUpdate,
)
from app.services.activity_service import ActivityService
from app.services.company_service import CompanyService
from app.services.contact_service import ContactService


class Tenant(TypedDict):
    organization: Organization
    users: dict[str, User]
    memberships: dict[str, Membership]


def _tenant(session: Session, label: str) -> Tenant:
    suffix = uuid4().hex
    organization = Organization(name=label, slug=f"{label.casefold()}-{suffix}")
    users = {
        role: User(
            email=f"{suffix}-{role.casefold()}@example.com",
            name=f"{label} {role.title()}",
            password_hash="test-hash",
        )
        for role in ("OWNER", "ADMIN", "MEMBER", "OTHER_MEMBER")
    }
    session.add(organization)
    session.add_all(users.values())
    session.flush()
    memberships = {
        role: Membership(
            organization_id=organization.id,
            user_id=user.id,
            role=MembershipRole(role if role != "OTHER_MEMBER" else "MEMBER"),
        )
        for role, user in users.items()
    }
    session.add_all(memberships.values())
    session.flush()
    session.commit()
    return {
        "organization": organization,
        "users": users,
        "memberships": memberships,
    }


def _membership(tenant: Tenant, role: str) -> Membership:
    return tenant["memberships"][role]


def _user(tenant: Tenant, role: str) -> User:
    return tenant["users"][role]


def _organization(tenant: Tenant) -> Organization:
    return tenant["organization"]


def _create_contact(
    service: ContactService,
    membership: Membership,
    name: str = "Ada Lovelace",
    **overrides: Any,
) -> Contact:
    return service.create(
        membership,
        ContactCreate(display_name=name, **overrides),
    )


def _contact_activity_events(
    session: Session, organization_id: str, contact_id: str
) -> list[ActivityEvent]:
    return list(
        session.query(ActivityEvent)
        .filter_by(
            organization_id=organization_id,
            entity_type=ActivityEntityType.CONTACT,
            entity_id=contact_id,
        )
        .all()
    )


def _assert_contact_activity(
    event: ActivityEvent,
    *,
    contact: Contact,
    actor_user_id: str,
    action: str,
) -> None:
    assert event.organization_id == contact.organization_id
    assert event.type == ActivityEventType.HUMAN_ACTION
    assert event.actor_type == ActivityActorType.USER
    assert event.actor_user_id == actor_user_id
    assert event.entity_type == ActivityEntityType.CONTACT
    assert event.entity_id == contact.id
    assert event.title == f"Contact {action.lower()}"
    assert event.summary == "A contact record was changed."
    assert event.status == action
    assert event.dedupe_key == f"contact:{contact.id}:{action}:r{contact.revision}"


def test_create_defaults_owner_and_allows_duplicate_emails(db: Session) -> None:
    tenant = _tenant(db, "Contact create")
    service = ContactService(db)
    member = _membership(tenant, "MEMBER")

    first = _create_contact(
        service,
        member,
        "  Ada Lovelace ",
        email=" SHARED@example.com ",
    )
    second = _create_contact(
        service,
        _membership(tenant, "ADMIN"),
        "Grace Hopper",
        email="shared@example.com",
    )

    assert first.display_name == "Ada Lovelace"
    assert first.owner_user_id == member.user_id
    assert first.source == ContactSource.MANUAL
    assert first.status == ContactStatus.ACTIVE
    assert second.email == first.email
    assert second.owner_user_id == _membership(tenant, "ADMIN").user_id


def test_contact_lifecycle_mutations_record_private_safe_activity_events(db: Session) -> None:
    tenant = _tenant(db, "Contact activity")
    owner = _membership(tenant, "OWNER")
    service = ContactService(db)
    private_values = (
        "Private Contact Name",
        "private-contact@example.com",
        "+1-555-0101",
        "Private contact description",
        "Updated Private Contact Name",
        "updated-private-contact@example.com",
        "+1-555-0102",
        "Updated private contact description",
    )

    contact = service.create(
        owner,
        ContactCreate(
            display_name=private_values[0],
            email=private_values[1],
            phone=private_values[2],
            description=private_values[3],
        ),
    )
    organization_id = _organization(tenant).id
    events = _contact_activity_events(db, organization_id, contact.id)
    assert len(events) == 1
    _assert_contact_activity(
        events[0],
        contact=contact,
        actor_user_id=owner.user_id,
        action="CREATED",
    )

    updated = service.update(
        owner,
        contact.id,
        ContactUpdate(
            expected_revision=1,
            display_name=private_values[4],
            email=private_values[5],
            phone=private_values[6],
            description=private_values[7],
        ),
    )
    events = _contact_activity_events(db, organization_id, contact.id)
    assert len(events) == 2
    updated_event = next(event for event in events if event.status == "UPDATED")
    _assert_contact_activity(
        updated_event,
        contact=updated,
        actor_user_id=owner.user_id,
        action="UPDATED",
    )

    no_op = service.update(
        owner,
        contact.id,
        ContactUpdate(
            expected_revision=2,
            display_name=private_values[4],
            email=private_values[5],
            phone=private_values[6],
            description=private_values[7],
        ),
    )
    assert no_op.revision == 2
    assert len(_contact_activity_events(db, organization_id, contact.id)) == 2

    archived = service.archive(owner, contact.id, expected_revision=2)
    events = _contact_activity_events(db, organization_id, contact.id)
    assert len(events) == 3
    archived_event = next(event for event in events if event.status == "ARCHIVED")
    _assert_contact_activity(
        archived_event,
        contact=archived,
        actor_user_id=owner.user_id,
        action="ARCHIVED",
    )

    repeated_archive = service.archive(owner, contact.id, expected_revision=3)
    assert repeated_archive.revision == 3
    assert len(_contact_activity_events(db, organization_id, contact.id)) == 3

    restored = service.restore(owner, contact.id, expected_revision=3)
    events = _contact_activity_events(db, organization_id, contact.id)
    assert len(events) == 4
    restored_event = next(event for event in events if event.status == "RESTORED")
    _assert_contact_activity(
        restored_event,
        contact=restored,
        actor_user_id=owner.user_id,
        action="RESTORED",
    )

    repeated_restore = service.restore(owner, contact.id, expected_revision=4)
    assert repeated_restore.revision == 4
    final_events = _contact_activity_events(db, organization_id, contact.id)
    assert len(final_events) == 4
    for event in final_events:
        assert all(value not in event.title + event.summary for value in private_values)
    assert {event.status for event in final_events} == {
        "CREATED",
        "UPDATED",
        "ARCHIVED",
        "RESTORED",
    }


def test_failed_contact_mutations_do_not_record_activity(db: Session) -> None:
    tenant = _tenant(db, "Contact activity failures")
    foreign_tenant = _tenant(db, "Foreign contact activity failures")
    owner = _membership(tenant, "OWNER")
    member = _membership(tenant, "MEMBER")
    other_member = _membership(tenant, "OTHER_MEMBER")
    foreign_owner = _membership(foreign_tenant, "OWNER")
    service = ContactService(db)
    contact = _create_contact(service, member, "Member-owned")
    foreign_contact = _create_contact(service, foreign_owner, "Foreign contact")

    with pytest.raises(ForbiddenError):
        service.update(
            other_member,
            contact.id,
            ContactUpdate(expected_revision=1, display_name="Unauthorized"),
        )
    with pytest.raises(ConflictError):
        service.update(
            owner,
            contact.id,
            ContactUpdate(expected_revision=2, display_name="Stale"),
        )
    with pytest.raises(NotFoundError):
        service.update(
            owner,
            foreign_contact.id,
            ContactUpdate(expected_revision=1, display_name="Cross-tenant"),
        )

    assert len(_contact_activity_events(db, _organization(tenant).id, contact.id)) == 1
    assert (
        len(
            _contact_activity_events(
                db,
                _organization(foreign_tenant).id,
                foreign_contact.id,
            )
        )
        == 1
    )


def test_contact_activity_failure_rolls_back_contact_mutation(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    tenant = _tenant(db, "Contact activity rollback")
    owner = _membership(tenant, "OWNER")
    service = ContactService(db)
    original_record = ActivityService.record

    def record_then_fail(activity_service: ActivityService, **kwargs: Any) -> ActivityEvent:
        original_record(activity_service, **kwargs)
        raise RuntimeError("Injected Activity recording failure")

    monkeypatch.setattr(ActivityService, "record", record_then_fail)
    with pytest.raises(RuntimeError, match="Injected Activity recording failure"):
        service.create(
            owner,
            ContactCreate(
                display_name="Uncommitted contact",
                email="uncommitted@example.com",
            ),
        )
    assert db.query(Contact).filter_by(organization_id=_organization(tenant).id).count() == 0
    assert db.query(ActivityEvent).filter_by(organization_id=_organization(tenant).id).count() == 0

    monkeypatch.setattr(ActivityService, "record", original_record)
    contact = _create_contact(service, owner, "Existing contact")
    monkeypatch.setattr(ActivityService, "record", record_then_fail)
    with pytest.raises(RuntimeError, match="Injected Activity recording failure"):
        service.update(
            owner,
            contact.id,
            ContactUpdate(expected_revision=1, display_name="Uncommitted update"),
        )

    db.expire_all()
    unchanged = service.get(owner, contact.id)
    assert unchanged.display_name == "Existing contact"
    assert unchanged.revision == 1
    events = _contact_activity_events(db, _organization(tenant).id, contact.id)
    assert len(events) == 1
    assert events[0].status == "CREATED"


def test_create_owner_permissions_and_same_tenant_references(db: Session) -> None:
    tenant = _tenant(db, "Contact ownership")
    foreign_tenant = _tenant(db, "Foreign ownership")
    service = ContactService(db)
    organization = _organization(tenant)
    foreign_organization = _organization(foreign_tenant)
    member = _membership(tenant, "MEMBER")
    admin = _membership(tenant, "ADMIN")
    foreign_owner = _user(foreign_tenant, "OWNER")
    company = Company(organization_id=organization.id, name="Valid Company")
    foreign_company = Company(
        organization_id=foreign_organization.id,
        name="Foreign Company",
    )
    db.add_all([company, foreign_company])
    db.commit()

    with pytest.raises(ForbiddenError):
        _create_contact(
            service,
            member,
            "Member supplied owner",
            owner_user_id=member.user_id,
        )

    assigned = _create_contact(
        service,
        admin,
        "Assigned contact",
        owner_user_id=member.user_id,
        company_id=company.id,
    )
    assert assigned.owner_user_id == member.user_id
    assert assigned.company_id == company.id

    with pytest.raises(NotFoundError):
        _create_contact(
            service,
            admin,
            "Foreign owner",
            owner_user_id=foreign_owner.id,
        )
    with pytest.raises(NotFoundError):
        _create_contact(
            service,
            admin,
            "Foreign company",
            company_id=foreign_company.id,
        )

    missing_company = str(uuid4())
    with pytest.raises(NotFoundError):
        _create_contact(service, admin, "Missing company", company_id=missing_company)


def test_archived_company_cannot_be_assigned_but_existing_contacts_are_preserved(
    db: Session,
) -> None:
    tenant = _tenant(db, "Archived company")
    service = ContactService(db)
    owner = _membership(tenant, "OWNER")
    organization = _organization(tenant)
    company = Company(organization_id=organization.id, name="Archivable")
    archived_company = Company(
        organization_id=organization.id,
        name="Already archived",
        archived_at=datetime.now(UTC),
    )
    db.add_all([company, archived_company])
    db.commit()

    with pytest.raises(ConflictError):
        _create_contact(
            service,
            owner,
            "New assignment",
            company_id=archived_company.id,
        )

    contact = _create_contact(service, owner, "Existing assignment", company_id=company.id)
    lead = Lead(organization_id=organization.id, name="Related lead")
    db.add(lead)
    db.commit()
    link = ContactLeadLinkRequest(
        expected_revision=1,
        lead_id=lead.id,
        linked=True,
    )
    service.set_lead_link(owner, contact.id, link)

    CompanyService(db).archive(
        organization.id,
        company.id,
        role=owner.role,
        actor_user_id=owner.user_id,
        expected_revision=1,
    )
    db.refresh(contact)
    assert contact.company_id == company.id
    assert service.list_leads(owner, contact.id).total == 1

    changed = service.update(
        owner,
        contact.id,
        ContactUpdate(expected_revision=2, display_name="Renamed existing assignment"),
    )
    assert changed.company_id == company.id


def test_read_access_filters_and_cross_tenant_references(db: Session) -> None:
    tenant = _tenant(db, "Contact reads")
    foreign_tenant = _tenant(db, "Foreign reads")
    service = ContactService(db)
    organization = _organization(tenant)
    foreign_organization = _organization(foreign_tenant)
    owner = _membership(tenant, "OWNER")
    member = _membership(tenant, "MEMBER")
    admin = _membership(tenant, "ADMIN")
    foreign_owner = _membership(foreign_tenant, "OWNER")

    company = Company(organization_id=organization.id, name="Scoped company")
    foreign_company = Company(
        organization_id=foreign_organization.id,
        name="Foreign company",
    )
    own_contact = _create_contact(service, member, "Member Contact", company_id=None)
    other_contact = _create_contact(service, admin, "Admin Contact")
    foreign_contact = _create_contact(
        service,
        foreign_owner,
        "Foreign Contact",
    )
    own_lead = Lead(organization_id=organization.id, name="Scoped lead")
    foreign_lead = Lead(organization_id=foreign_organization.id, name="Foreign lead")
    db.add_all([company, foreign_company, own_lead, foreign_lead])
    db.commit()
    service.set_lead_link(
        member,
        own_contact.id,
        ContactLeadLinkRequest(expected_revision=1, lead_id=own_lead.id, linked=True),
    )

    for role in (owner, admin, member):
        assert service.list(role).total == 2
        assert service.get(role, other_contact.id).id == other_contact.id

    assert service.list(owner, company_id=company.id).total == 0
    assert service.list(owner, lead_id=own_lead.id).total == 1
    assert service.list(owner, owner_user_id=member.user_id).total == 1

    with pytest.raises(NotFoundError):
        service.get(owner, foreign_contact.id)
    with pytest.raises(NotFoundError):
        service.list(owner, company_id=foreign_company.id)
    with pytest.raises(NotFoundError):
        service.list(owner, lead_id=foreign_lead.id)
    with pytest.raises(NotFoundError):
        service.list(owner, owner_user_id=_user(foreign_tenant, "OWNER").id)


def test_updates_enforce_ownership_and_revision_only_on_change(db: Session) -> None:
    tenant = _tenant(db, "Contact updates")
    service = ContactService(db)
    owner = _membership(tenant, "OWNER")
    admin = _membership(tenant, "ADMIN")
    member = _membership(tenant, "MEMBER")
    other_member = _membership(tenant, "OTHER_MEMBER")
    contact = _create_contact(service, member, "Member-owned")

    with pytest.raises(ForbiddenError):
        service.update(
            other_member,
            contact.id,
            ContactUpdate(expected_revision=1, display_name="Forbidden"),
        )
    with pytest.raises(ForbiddenError):
        service.update(
            member,
            contact.id,
            ContactUpdate(expected_revision=1, owner_user_id=member.user_id),
        )

    no_op = service.update(
        member,
        contact.id,
        ContactUpdate(expected_revision=1, display_name="Member-owned"),
    )
    assert no_op.revision == 1

    updated = service.update(
        owner,
        contact.id,
        ContactUpdate(expected_revision=1, display_name="Updated"),
    )
    assert updated.revision == 2
    assert updated.display_name == "Updated"

    admin_updated = service.update(
        admin,
        contact.id,
        ContactUpdate(expected_revision=2, description="Admin edit"),
    )
    assert admin_updated.revision == 3
    assert admin_updated.description == "Admin edit"

    with pytest.raises(ConflictError) as stale:
        service.update(
            owner,
            contact.id,
            ContactUpdate(expected_revision=2, display_name="Stale"),
        )
    assert stale.value.content["current_revision"] == 3


def test_list_validates_pagination_and_foreign_owner_filters(db: Session) -> None:
    tenant = _tenant(db, "Contact pagination")
    foreign_tenant = _tenant(db, "Foreign contact pagination")
    service = ContactService(db)
    owner = _membership(tenant, "OWNER")
    with pytest.raises(UnprocessableError):
        service.list(owner, limit=0)
    with pytest.raises(UnprocessableError):
        service.list(owner, limit=101)
    with pytest.raises(UnprocessableError):
        service.list(owner, offset=-1)
    with pytest.raises(NotFoundError):
        service.list(owner, owner_user_id=_user(foreign_tenant, "OWNER").id)


def test_archive_restore_permissions_revisions_and_archived_edit_block(db: Session) -> None:
    tenant = _tenant(db, "Contact archive")
    service = ContactService(db)
    owner = _membership(tenant, "OWNER")
    admin = _membership(tenant, "ADMIN")
    member = _membership(tenant, "MEMBER")
    contact = _create_contact(service, member, "Archivable")
    lead = Lead(organization_id=_organization(tenant).id, name="Existing lead")
    db.add(lead)
    db.commit()
    service.set_lead_link(
        owner,
        contact.id,
        ContactLeadLinkRequest(expected_revision=1, lead_id=lead.id, linked=True),
    )

    with pytest.raises(ForbiddenError):
        service.archive(member, contact.id, expected_revision=1)
    with pytest.raises(ForbiddenError):
        service.restore(member, contact.id, expected_revision=2)

    archived = service.archive(owner, contact.id, expected_revision=2)
    assert archived.archived_at is not None
    assert archived.revision == 3
    assert service.list(owner).total == 0
    assert service.list(owner, include_archived=True).total == 1

    repeated = service.archive(admin, contact.id, expected_revision=3)
    assert repeated.revision == 3
    with pytest.raises(ConflictError) as stale:
        service.archive(owner, contact.id, expected_revision=2)
    assert stale.value.content["current_revision"] == 3

    with pytest.raises(ConflictError):
        service.update(
            owner,
            contact.id,
            ContactUpdate(expected_revision=3, display_name="Archived edit"),
        )
    with pytest.raises(ConflictError):
        service.set_lead_link(
            owner,
            contact.id,
            ContactLeadLinkRequest(
                expected_revision=3,
                lead_id=lead.id,
                linked=True,
            ),
        )
    with pytest.raises(ConflictError):
        service.set_lead_link(
            owner,
            contact.id,
            ContactLeadLinkRequest(
                expected_revision=3,
                lead_id=lead.id,
                linked=False,
            ),
        )

    restored = service.restore(owner, contact.id, expected_revision=3)
    assert restored.archived_at is None
    assert restored.revision == 4
    repeated_restore = service.restore(admin, contact.id, expected_revision=4)
    assert repeated_restore.revision == 4
    assert service.list_leads(owner, contact.id).total == 1


def test_lead_associations_are_tenant_scoped_revisioned_and_idempotent(db: Session) -> None:
    tenant = _tenant(db, "Contact leads")
    foreign_tenant = _tenant(db, "Foreign contact leads")
    service = ContactService(db)
    owner = _membership(tenant, "OWNER")
    member = _membership(tenant, "MEMBER")
    other_member = _membership(tenant, "OTHER_MEMBER")
    organization = _organization(tenant)
    foreign_organization = _organization(foreign_tenant)
    contact = _create_contact(service, member, "Owned contact")
    another_contact = _create_contact(service, other_member, "Other contact")
    lead = Lead(organization_id=organization.id, name="Local lead")
    foreign_lead = Lead(
        organization_id=foreign_organization.id,
        name="Foreign lead",
    )
    db.add_all([lead, foreign_lead])
    db.commit()

    linked = service.set_lead_link(
        member,
        contact.id,
        ContactLeadLinkRequest(expected_revision=1, lead_id=lead.id, linked=True),
    )
    assert linked.linked is True
    assert linked.revision == 2

    repeated_link = service.set_lead_link(
        member,
        contact.id,
        ContactLeadLinkRequest(expected_revision=2, lead_id=lead.id, linked=True),
    )
    assert repeated_link.revision == 2
    assert service.list_leads(member, contact.id).total == 1

    with pytest.raises(ConflictError):
        service.set_lead_link(
            member,
            contact.id,
            ContactLeadLinkRequest(expected_revision=1, lead_id=lead.id, linked=False),
        )
    with pytest.raises(ForbiddenError):
        service.set_lead_link(
            member,
            another_contact.id,
            ContactLeadLinkRequest(expected_revision=1, lead_id=lead.id, linked=True),
        )
    with pytest.raises(NotFoundError):
        service.set_lead_link(
            member,
            contact.id,
            ContactLeadLinkRequest(
                expected_revision=2,
                lead_id=foreign_lead.id,
                linked=True,
            ),
        )

    unlinked = service.set_lead_link(
        member,
        contact.id,
        ContactLeadLinkRequest(expected_revision=2, lead_id=lead.id, linked=False),
    )
    assert unlinked.linked is False
    assert unlinked.revision == 3

    repeated_unlink = service.set_lead_link(
        member,
        contact.id,
        ContactLeadLinkRequest(expected_revision=3, lead_id=lead.id, linked=False),
    )
    assert repeated_unlink.revision == 3
    assert service.list_leads(member, contact.id).total == 0

    with pytest.raises(NotFoundError):
        service.list_leads(owner, str(uuid4()))


def test_linked_lead_listing_uses_bounded_pagination(db: Session) -> None:
    tenant = _tenant(db, "Contact lead pages")
    service = ContactService(db)
    owner = _membership(tenant, "OWNER")
    organization = _organization(tenant)
    contact = _create_contact(service, owner)
    leads = [
        Lead(organization_id=organization.id, name=f"Lead {index}")
        for index in range(25)
    ]
    db.add_all(leads)
    db.flush()
    repository = ContactRepository(db)
    for lead in leads:
        assert repository.link_to_lead(organization.id, contact.id, lead.id)
    db.commit()

    first_page = service.list_leads(owner, contact.id)
    second_page = service.list_leads(owner, contact.id, limit=10, offset=20)
    assert first_page.limit == 20
    assert len(first_page.items) == 20
    assert first_page.total == 25
    assert len(second_page.items) == 5
    assert second_page.total == 25

    with pytest.raises(UnprocessableError):
        service.list_leads(owner, contact.id, limit=101)

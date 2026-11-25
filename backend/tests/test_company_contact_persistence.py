from datetime import datetime
from uuid import uuid4

import pytest
from sqlalchemy import insert, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.company import Company, CompanyLifecycleStatus, CompanySource
from app.models.contact import Contact, ContactSource, ContactStatus
from app.models.contact_lead import contact_leads
from app.models.lead import Lead
from app.models.membership import Membership, MembershipRole
from app.models.organization import Organization
from app.models.user import User
from app.repositories.company_repository import CompanyRepository
from app.repositories.contact_repository import ContactRepository


def _tenant(session: Session, label: str) -> tuple[Organization, User]:
    suffix = uuid4().hex
    organization = Organization(name=label, slug=f"{label.casefold()}-{suffix}")
    user = User(
        email=f"{suffix}@example.com",
        name=f"{label} Owner",
        password_hash="test-hash",
    )
    session.add_all([organization, user])
    session.flush()
    session.add(
        Membership(
            organization_id=organization.id,
            user_id=user.id,
            role=MembershipRole.OWNER,
        )
    )
    session.flush()
    return organization, user


def test_company_and_contact_defaults_and_relationships(db: Session) -> None:
    organization, owner = _tenant(db, "Acme")
    company = Company(
        organization_id=organization.id,
        name="Acme",
        owner_user_id=owner.id,
    )
    db.add(company)
    db.flush()

    contact = Contact(
        organization_id=organization.id,
        display_name="Ada Lovelace",
        company_id=company.id,
        owner_user_id=owner.id,
        email="ada@example.com",
    )
    db.add(contact)
    db.flush()

    assert company.lifecycle_status == CompanyLifecycleStatus.PROSPECT
    assert company.source == CompanySource.MANUAL
    assert company.revision == 1
    assert company.archived_at is None
    assert company.created_at is not None
    assert company.updated_at is not None
    assert contact.status == ContactStatus.ACTIVE
    assert contact.source == ContactSource.MANUAL
    assert contact.revision == 1
    assert contact.archived_at is None
    assert contact.company is not None
    assert contact.company.id == company.id
    assert [row.id for row in company.contacts] == [contact.id]


@pytest.mark.parametrize(
    "overrides",
    [
        {"name": "  "},
        {"employee_count": -1},
        {"website_domain": "EXAMPLE.COM"},
        {"lifecycle_status": "INVALID"},
        {"source": "INVALID"},
        {"revision": 0},
    ],
)
def test_company_database_checks(db: Session, overrides: dict[str, object]) -> None:
    organization, _ = _tenant(db, "Company checks")
    values: dict[str, object] = {
        "organization_id": organization.id,
        "name": "Example Company",
    }
    values.update(overrides)
    db.add(Company(**values))  # type: ignore[arg-type]

    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()


@pytest.mark.parametrize(
    "overrides",
    [
        {"display_name": " "},
        {"email": "Ada@Example.com"},
        {"status": "INVALID"},
        {"source": "INVALID"},
        {"revision": 0},
    ],
)
def test_contact_database_checks(db: Session, overrides: dict[str, object]) -> None:
    organization, _ = _tenant(db, "Contact checks")
    values: dict[str, object] = {
        "organization_id": organization.id,
        "display_name": "Ada Lovelace",
    }
    values.update(overrides)
    db.add(Contact(**values))  # type: ignore[arg-type]

    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()


def test_repositories_scope_filter_search_order_and_page(db: Session) -> None:
    organization, owner = _tenant(db, "Directory")
    other_organization, _ = _tenant(db, "Other")
    base = datetime(2026, 1, 1)

    older = Company(
        organization_id=organization.id,
        name="Alpha Works",
        lifecycle_status=CompanyLifecycleStatus.PROSPECT,
        owner_user_id=owner.id,
        created_at=base,
    )
    newer = Company(
        organization_id=organization.id,
        name="Beta Systems",
        website_domain="beta.example",
        lifecycle_status=CompanyLifecycleStatus.CUSTOMER,
        owner_user_id=owner.id,
        created_at=base.replace(day=2),
    )
    archived = Company(
        organization_id=organization.id,
        name="Archived Company",
        archived_at=base,
        created_at=base,
    )
    foreign = Company(
        organization_id=other_organization.id,
        name="Alpha Works",
        created_at=base.replace(day=3),
    )
    db.add_all([older, newer, archived, foreign])
    db.flush()

    contact_older = Contact(
        organization_id=organization.id,
        display_name="Ada Lovelace",
        email="ada@example.com",
        company_id=older.id,
        owner_user_id=owner.id,
        created_at=base,
    )
    contact_newer = Contact(
        organization_id=organization.id,
        display_name="Grace Hopper",
        email="grace@example.com",
        company_id=newer.id,
        status=ContactStatus.INACTIVE,
        owner_user_id=owner.id,
        created_at=base.replace(day=2),
    )
    contact_archived = Contact(
        organization_id=organization.id,
        display_name="Archived Contact",
        archived_at=base,
        created_at=base,
    )
    contact_foreign = Contact(
        organization_id=other_organization.id,
        display_name="Ada Lovelace",
        email="ada@example.com",
        created_at=base.replace(day=3),
    )
    db.add_all([contact_older, contact_newer, contact_archived, contact_foreign])
    db.flush()

    companies, total = CompanyRepository(db).list_for_organization(
        organization.id,
        search="BETA",
        lifecycle_status=CompanyLifecycleStatus.CUSTOMER,
        owner_user_id=owner.id,
        limit=10,
        offset=0,
    )
    assert total == 1
    assert [row.id for row in companies] == [newer.id]

    company_page, company_total = CompanyRepository(db).list_for_organization(
        organization.id,
        search=None,
        lifecycle_status=None,
        owner_user_id=None,
        limit=1,
        offset=0,
    )
    assert company_total == 2
    assert [row.id for row in company_page] == [newer.id]
    assert CompanyRepository(db).get_by_id(other_organization.id, older.id) is None
    assert CompanyRepository(db).get_by_ids(other_organization.id, [older.id, foreign.id]) == {
        foreign.id: foreign
    }

    contacts, contact_total = ContactRepository(db).list_for_organization(
        organization.id,
        search="ADA",
        company_id=older.id,
        status=ContactStatus.ACTIVE,
        owner_user_id=owner.id,
        limit=10,
        offset=0,
    )
    assert contact_total == 1
    assert [row.id for row in contacts] == [contact_older.id]

    contact_page, page_total = ContactRepository(db).list_for_organization(
        organization.id,
        search=None,
        company_id=None,
        status=None,
        owner_user_id=None,
        limit=1,
        offset=0,
    )
    assert page_total == 2
    assert [row.id for row in contact_page] == [contact_newer.id]
    assert ContactRepository(db).get_by_id(other_organization.id, contact_older.id) is None
    assert ContactRepository(db).get_by_ids(
        other_organization.id, [contact_older.id, contact_foreign.id]
    ) == {contact_foreign.id: contact_foreign}
    assert ContactRepository(db).list_by_emails(organization.id, {" ADA@EXAMPLE.COM "}) == [
        contact_older
    ]
    assert ContactRepository(db).list_for_company(
        organization.id, older.id, limit=10, offset=0
    ) == ([contact_older], 1)

    archived_companies, archived_company_total = CompanyRepository(db).list_for_organization(
        organization.id,
        search="Archived",
        lifecycle_status=None,
        owner_user_id=None,
        include_archived=True,
        limit=10,
        offset=0,
    )
    assert archived_company_total == 1
    assert [row.id for row in archived_companies] == [archived.id]

    archived_contacts, archived_contact_total = ContactRepository(db).list_for_organization(
        organization.id,
        search="Archived",
        company_id=None,
        status=None,
        owner_user_id=None,
        include_archived=True,
        limit=10,
        offset=0,
    )
    assert archived_contact_total == 1
    assert [row.id for row in archived_contacts] == [contact_archived.id]


def test_company_domain_and_contact_email_are_not_unique(db: Session) -> None:
    organization, _ = _tenant(db, "Duplicate signals")
    db.add_all(
        [
            Company(organization_id=organization.id, name="Acme North", website_domain="acme.test"),
            Company(organization_id=organization.id, name="Acme South", website_domain="acme.test"),
            Contact(
                organization_id=organization.id,
                display_name="Shared inbox contact one",
                email="shared@example.com",
            ),
            Contact(
                organization_id=organization.id,
                display_name="Shared inbox contact two",
                email="shared@example.com",
            ),
        ]
    )
    db.flush()

    assert db.scalar(select(Company.id).where(Company.name == "Acme North")) is not None


def test_contact_lead_relationships_are_many_to_many_and_tenant_scoped(db: Session) -> None:
    organization, _ = _tenant(db, "Contact leads")
    other_organization, _ = _tenant(db, "Other contact leads")
    contact_one = Contact(organization_id=organization.id, display_name="Contact One")
    contact_two = Contact(organization_id=organization.id, display_name="Contact Two")
    foreign_contact = Contact(
        organization_id=other_organization.id,
        display_name="Foreign Contact",
    )
    lead_one = Lead(
        id="00000000-0000-0000-0000-000000000001",
        organization_id=organization.id,
        name="Lead One",
        created_at=datetime(2026, 1, 1),
    )
    lead_two = Lead(
        id="00000000-0000-0000-0000-000000000002",
        organization_id=organization.id,
        name="Lead Two",
        created_at=datetime(2026, 1, 1),
    )
    foreign_lead = Lead(organization_id=other_organization.id, name="Foreign Lead")
    db.add_all(
        [
            contact_one,
            contact_two,
            foreign_contact,
            lead_one,
            lead_two,
            foreign_lead,
        ]
    )
    db.flush()

    repository = ContactRepository(db)
    assert repository.link_to_lead(organization.id, contact_one.id, lead_one.id)
    assert repository.link_to_lead(organization.id, contact_one.id, lead_two.id)
    assert repository.link_to_lead(organization.id, contact_two.id, lead_one.id)
    assert not repository.link_to_lead(organization.id, contact_one.id, foreign_lead.id)
    assert not repository.link_to_lead(organization.id, foreign_contact.id, lead_one.id)
    assert not repository.link_to_lead(organization.id, contact_one.id, lead_one.id)

    lead_page, lead_total = repository.list_leads_for_contact(
        organization.id,
        contact_one.id,
        limit=1,
        offset=0,
    )
    assert lead_total == 2
    assert [lead.id for lead in lead_page] == [lead_two.id]
    second_lead_page, second_lead_total = repository.list_leads_for_contact(
        organization.id,
        contact_one.id,
        limit=1,
        offset=1,
    )
    assert second_lead_total == 2
    assert [lead.id for lead in second_lead_page] == [lead_one.id]
    foreign_lead_page, foreign_lead_total = repository.list_leads_for_contact(
        organization.id,
        foreign_contact.id,
        limit=10,
        offset=0,
    )
    assert foreign_lead_page == []
    assert foreign_lead_total == 0
    other_tenant_page, other_tenant_total = repository.list_leads_for_contact(
        other_organization.id,
        contact_one.id,
        limit=10,
        offset=0,
    )
    assert other_tenant_page == []
    assert other_tenant_total == 0
    assert {contact.id for contact in repository.list_contacts_for_lead(
        organization.id, lead_one.id
    )} == {contact_one.id, contact_two.id}
    assert {lead.id for lead in contact_one.leads} == {lead_one.id, lead_two.id}
    assert {contact.id for contact in lead_one.contacts} == {contact_one.id, contact_two.id}

    contacts, total = repository.list_for_organization(
        organization.id,
        search=None,
        company_id=None,
        status=None,
        owner_user_id=None,
        lead_id=lead_one.id,
        limit=10,
        offset=0,
    )
    assert total == 2
    assert {contact.id for contact in contacts} == {contact_one.id, contact_two.id}

    assert repository.unlink_from_lead(organization.id, contact_one.id, lead_one.id)
    assert not repository.unlink_from_lead(organization.id, contact_one.id, lead_one.id)


def test_contact_lead_associations_reject_duplicate_rows(db: Session) -> None:
    organization, _ = _tenant(db, "Contact lead uniqueness")
    contact = Contact(organization_id=organization.id, display_name="Unique Contact")
    lead = Lead(organization_id=organization.id, name="Unique Lead")
    db.add_all([contact, lead])
    db.flush()
    assert ContactRepository(db).link_to_lead(organization.id, contact.id, lead.id)
    db.commit()

    with pytest.raises(IntegrityError):
        db.execute(
            insert(contact_leads).values(
                organization_id=organization.id,
                contact_id=contact.id,
                lead_id=lead.id,
            )
        )
        db.flush()
    db.rollback()

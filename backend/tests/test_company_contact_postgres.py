"""PostgreSQL-only migration and composite foreign-key checks for CRM foundations."""

import os
import subprocess
import sys
from collections.abc import Generator
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, insert, inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.models.company import Company
from app.models.contact import Contact
from app.models.contact_lead import contact_leads
from app.models.lead import Lead
from app.models.membership import Membership, MembershipRole
from app.models.organization import Organization
from app.models.user import User
from app.repositories.contact_repository import ContactRepository
from tests.postgres_guard import postgres_test_url, requires_postgres

pytestmark = requires_postgres

BACKEND_DIR = Path(__file__).resolve().parents[1]


def _schema_url(schema: str) -> str:
    url = postgres_test_url()
    separator = "&" if "?" in url else "?"
    return f"{url}{separator}options=-csearch_path%3D{schema}"


@pytest.fixture
def schema() -> Generator[str, None, None]:
    name = f"company_contact_test_{uuid4().hex[:10]}"
    admin = create_engine(postgres_test_url())
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
        postgres_test_url(),
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
        [
            sys.executable,
            "-m",
            "alembic",
            "-c",
            str(BACKEND_DIR / "alembic.ini"),
            *args,
        ],
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert result.returncode == 0, result.stderr[-2000:]


def _org_with_owner(session: Session, label: str) -> tuple[Organization, User]:
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
    session.commit()
    return organization, user


def test_company_contact_migration_upgrade_and_downgrade(schema: str) -> None:
    _alembic(schema, "upgrade", "047_growth_p2_mvps")
    _alembic(schema, "upgrade", "051_contact_lead_associations")

    engine = create_engine(
        postgres_test_url(),
        connect_args={"options": f"-csearch_path={schema}"},
    )
    try:
        inspector = inspect(engine)
        assert {"companies", "contacts", "contact_leads"} <= set(inspector.get_table_names())
        with engine.connect() as connection:
            assert (
                connection.execute(text("SELECT version_num FROM alembic_version")).scalar()
                == "051_contact_lead_associations"
            )

        company_checks = {
            constraint["name"] for constraint in inspector.get_check_constraints("companies")
        }
        assert {
            "ck_companies_name_nonblank",
            "ck_companies_employee_count_nonnegative",
            "ck_companies_website_domain_normalized",
            "ck_companies_lifecycle_status",
            "ck_companies_source",
            "ck_companies_revision_positive",
        } <= company_checks
        company_fks = {constraint["name"] for constraint in inspector.get_foreign_keys("companies")}
        assert {
            "fk_companies_organization",
            "fk_companies_owner_membership",
        } <= company_fks
        company_indexes = {index["name"] for index in inspector.get_indexes("companies")}
        assert {
            "ix_companies_organization_created_at_id",
            "ix_companies_organization_lifecycle_status_created_at_id",
            "ix_companies_organization_owner_user_id",
            "ix_companies_organization_website_domain",
            "ix_companies_organization_name",
        } <= company_indexes

        contact_checks = {
            constraint["name"] for constraint in inspector.get_check_constraints("contacts")
        }
        assert {
            "ck_contacts_display_name_nonblank",
            "ck_contacts_email_normalized",
            "ck_contacts_status",
            "ck_contacts_source",
            "ck_contacts_revision_positive",
        } <= contact_checks
        contact_fks = {constraint["name"] for constraint in inspector.get_foreign_keys("contacts")}
        assert {
            "fk_contacts_organization",
            "fk_contacts_company_organization",
            "fk_contacts_owner_membership",
        } <= contact_fks
        contact_indexes = {index["name"] for index in inspector.get_indexes("contacts")}
        assert {
            "ix_contacts_organization_created_at_id",
            "ix_contacts_organization_company_created_at_id",
            "ix_contacts_organization_status_created_at_id",
            "ix_contacts_organization_owner_user_id",
            "ix_contacts_organization_email",
            "ix_contacts_organization_display_name",
            "ix_contacts_organization_phone",
        } <= contact_indexes

        association_fks = {
            constraint["name"]: constraint
            for constraint in inspector.get_foreign_keys("contact_leads")
        }
        assert {
            "fk_contact_leads_organization",
            "fk_contact_leads_contact_organization",
            "fk_contact_leads_lead_organization",
        } <= set(association_fks)
        assert association_fks["fk_contact_leads_contact_organization"][
            "constrained_columns"
        ] == ["organization_id", "contact_id"]
        assert association_fks["fk_contact_leads_lead_organization"][
            "constrained_columns"
        ] == ["organization_id", "lead_id"]
        assert inspector.get_pk_constraint("contact_leads")["constrained_columns"] == [
            "organization_id",
            "contact_id",
            "lead_id",
        ]
        assert "ix_contact_leads_organization_lead_contact" in {
            index["name"] for index in inspector.get_indexes("contact_leads")
        }

        _alembic(schema, "downgrade", "050_follow_up_sequence")
        assert "contact_leads" not in set(inspect(engine).get_table_names())
        assert {"companies", "contacts"} <= set(inspect(engine).get_table_names())
        _alembic(schema, "upgrade", "051_contact_lead_associations")
        assert "contact_leads" in set(inspect(engine).get_table_names())

        _alembic(schema, "downgrade", "047_growth_p2_mvps")
        assert not {"companies", "contacts", "contact_leads"} & set(
            inspect(engine).get_table_names()
        )
        _alembic(schema, "upgrade", "051_contact_lead_associations")
        assert {"companies", "contacts", "contact_leads"} <= set(inspect(engine).get_table_names())
    finally:
        engine.dispose()


def test_composite_owner_and_company_foreign_keys_are_enforced(
    pg_session: Session,
) -> None:
    organization_a, user_a = _org_with_owner(pg_session, "Alpha")
    organization_b, user_b = _org_with_owner(pg_session, "Beta")

    company_a = Company(
        organization_id=organization_a.id,
        name="Alpha Company",
        owner_user_id=user_a.id,
    )
    company_b = Company(
        organization_id=organization_b.id,
        name="Beta Company",
        owner_user_id=user_b.id,
    )
    pg_session.add_all([company_a, company_b])
    pg_session.commit()

    pg_session.add(
        Company(
            organization_id=organization_a.id,
            name="Wrong-tenant owner",
            owner_user_id=user_b.id,
        )
    )
    with pytest.raises(IntegrityError):
        pg_session.commit()
    pg_session.rollback()

    pg_session.add(
        Contact(
            organization_id=organization_a.id,
            display_name="Wrong-tenant owner",
            owner_user_id=user_b.id,
        )
    )
    with pytest.raises(IntegrityError):
        pg_session.commit()
    pg_session.rollback()

    pg_session.add(
        Contact(
            organization_id=organization_a.id,
            display_name="Wrong-tenant company",
            company_id=company_b.id,
        )
    )
    with pytest.raises(IntegrityError):
        pg_session.commit()
    pg_session.rollback()

    contact = Contact(
        organization_id=organization_a.id,
        display_name="Valid Contact",
        company_id=company_a.id,
        owner_user_id=user_a.id,
    )
    pg_session.add(contact)
    pg_session.commit()
    assert contact.id is not None


def test_company_domain_and_contact_email_are_non_unique(pg_session: Session) -> None:
    organization, _ = _org_with_owner(pg_session, "Duplicates")
    pg_session.add_all(
        [
            Company(
                organization_id=organization.id,
                name="North",
                website_domain="shared.example",
            ),
            Company(
                organization_id=organization.id,
                name="South",
                website_domain="shared.example",
            ),
            Contact(
                organization_id=organization.id,
                display_name="Contact One",
                email="shared@example.com",
            ),
            Contact(
                organization_id=organization.id,
                display_name="Contact Two",
                email="shared@example.com",
            ),
        ]
    )
    pg_session.commit()


def test_contact_lead_associations_are_unique_and_tenant_scoped(pg_session: Session) -> None:
    organization_a, _ = _org_with_owner(pg_session, "Contact Lead Alpha")
    organization_b, _ = _org_with_owner(pg_session, "Contact Lead Beta")
    contact_a = Contact(organization_id=organization_a.id, display_name="Contact A")
    contact_a_two = Contact(organization_id=organization_a.id, display_name="Contact A Two")
    contact_b = Contact(organization_id=organization_b.id, display_name="Contact B")
    lead_a = Lead(organization_id=organization_a.id, name="Lead A")
    lead_a_two = Lead(organization_id=organization_a.id, name="Lead A Two")
    lead_b = Lead(organization_id=organization_b.id, name="Lead B")
    pg_session.add_all([contact_a, contact_a_two, contact_b, lead_a, lead_a_two, lead_b])
    pg_session.commit()

    repository = ContactRepository(pg_session)
    assert repository.link_to_lead(organization_a.id, contact_a.id, lead_a.id)
    assert repository.link_to_lead(organization_a.id, contact_a.id, lead_a_two.id)
    assert repository.link_to_lead(organization_a.id, contact_a_two.id, lead_a.id)
    assert repository.link_to_lead(organization_a.id, contact_b.id, lead_a.id) is False
    assert repository.link_to_lead(organization_a.id, contact_a.id, lead_b.id) is False
    assert repository.link_to_lead(organization_b.id, contact_b.id, lead_b.id)
    pg_session.commit()

    with pytest.raises(IntegrityError):
        pg_session.execute(
            insert(contact_leads).values(
                organization_id=organization_a.id,
                contact_id=contact_b.id,
                lead_id=lead_a.id,
            )
        )
        pg_session.commit()
    pg_session.rollback()

    with pytest.raises(IntegrityError):
        pg_session.execute(
            insert(contact_leads).values(
                organization_id=organization_a.id,
                contact_id=contact_a.id,
                lead_id=lead_b.id,
            )
        )
        pg_session.commit()
    pg_session.rollback()

    with pytest.raises(IntegrityError):
        pg_session.execute(
            insert(contact_leads).values(
                organization_id=organization_a.id,
                contact_id=contact_a.id,
                lead_id=lead_a.id,
            )
        )
        pg_session.commit()
    pg_session.rollback()

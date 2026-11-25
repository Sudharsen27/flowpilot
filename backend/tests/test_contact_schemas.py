from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.schemas.contacts import (
    CONTACT_LIST_MAX_LIMIT,
    LINKED_LEAD_LIST_DEFAULT_LIMIT,
    LINKED_LEAD_LIST_MAX_LIMIT,
    ContactCreate,
    ContactLeadLinkRequest,
    ContactLeadLinkResponse,
    ContactListResponse,
    ContactPublic,
    ContactRevisionRequest,
    ContactUpdate,
    LinkedLeadListResponse,
    LinkedLeadSummary,
)


def test_contact_create_normalizes_optional_fields_and_email() -> None:
    contact = ContactCreate(
        display_name="  Ada Lovelace  ",
        first_name=" Ada ",
        email=" Ada@Example.com ",
        phone=" ",
        company_id=" company-123 ",
    )

    assert contact.display_name == "Ada Lovelace"
    assert contact.first_name == "Ada"
    assert str(contact.email) == "ada@example.com"
    assert contact.phone is None
    assert contact.company_id == "company-123"
    assert contact.status == "ACTIVE"


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"display_name": "   "},
        {"display_name": "Valid", "email": "not-an-email"},
        {"display_name": "Valid", "source": "API"},
        {"display_name": "Valid", "revision": 8},
        {"display_name": "Valid", "organization_id": "tenant-id"},
        {"display_name": "x" * 201},
        {"display_name": "Valid", "first_name": "x" * 121},
        {"display_name": "Valid", "email": "a@example.com", "phone": "x" * 41},
        {"display_name": "Valid", "company_id": "x" * 37},
    ],
)
def test_contact_create_rejects_invalid_or_server_controlled_fields(
    payload: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        ContactCreate.model_validate(payload)


def test_duplicate_contact_emails_are_allowed_by_the_schema() -> None:
    first = ContactCreate(display_name="First", email="shared@example.com")
    second = ContactCreate(display_name="Second", email="shared@example.com")

    assert first.email == second.email


def test_contact_update_requires_revision_and_rejects_clearing_required_fields() -> None:
    with pytest.raises(ValidationError):
        ContactUpdate.model_validate({"display_name": "Updated"})
    with pytest.raises(ValidationError):
        ContactUpdate.model_validate({"expected_revision": 0})
    with pytest.raises(ValidationError):
        ContactUpdate.model_validate({"expected_revision": 1, "display_name": None})
    with pytest.raises(ValidationError):
        ContactUpdate.model_validate({"expected_revision": 1, "status": None})
    with pytest.raises(ValidationError):
        ContactUpdate.model_validate({"expected_revision": 1, "archived_at": None})

    update = ContactUpdate.model_validate(
        {"expected_revision": 3, "display_name": "  Ada  ", "email": ""}
    )
    assert update.expected_revision == 3
    assert update.display_name == "Ada"
    assert update.email is None


def test_contact_revision_and_link_requests_are_strict() -> None:
    assert ContactRevisionRequest(expected_revision=1).expected_revision == 1
    with pytest.raises(ValidationError):
        ContactRevisionRequest.model_validate({})
    with pytest.raises(ValidationError):
        ContactRevisionRequest.model_validate({"expected_revision": 1, "archived_at": None})

    request = ContactLeadLinkRequest(
        expected_revision=2,
        lead_id=" lead-id ",
        linked=True,
    )
    assert request.lead_id == "lead-id"
    with pytest.raises(ValidationError):
        ContactLeadLinkRequest.model_validate(
            {"lead_id": "lead-id", "linked": True}
        )
    with pytest.raises(ValidationError):
        ContactLeadLinkRequest.model_validate(
            {
                "expected_revision": 1,
                "lead_id": "lead-id",
                "linked": True,
                "organization_id": "tenant-id",
            }
        )
    with pytest.raises(ValidationError):
        ContactLeadLinkRequest.model_validate(
            {"expected_revision": 1, "lead_id": " ", "linked": False}
        )

    response = ContactLeadLinkResponse(
        contact_id="contact-id",
        lead_id="lead-id",
        linked=False,
        revision=4,
    )
    assert response.revision == 4
    assert "organization_id" not in response.model_dump()


def test_list_responses_enforce_bounded_pagination() -> None:
    assert LINKED_LEAD_LIST_DEFAULT_LIMIT == 20
    assert LINKED_LEAD_LIST_MAX_LIMIT == 100
    assert CONTACT_LIST_MAX_LIMIT == 100

    response = LinkedLeadListResponse(items=[], total=0)
    assert response.limit == 20
    assert response.offset == 0

    with pytest.raises(ValidationError):
        LinkedLeadListResponse(items=[], limit=101, total=0)
    with pytest.raises(ValidationError):
        LinkedLeadListResponse(items=[], limit=20, offset=-1, total=0)
    with pytest.raises(ValidationError):
        ContactListResponse(items=[], limit=0, offset=0, total=0)


def test_public_responses_omit_organization_and_private_lead_fields() -> None:
    timestamp = datetime(2026, 1, 1, tzinfo=UTC)
    contact = ContactPublic.model_validate(
        SimpleNamespace(
            id="contact-id",
            organization_id="tenant-secret",
            display_name="Ada Lovelace",
            first_name="Ada",
            last_name="Lovelace",
            job_title="Engineer",
            email="ada@example.com",
            phone=None,
            mobile=None,
            linkedin_url=None,
            company_id=None,
            owner_user_id=None,
            source="MANUAL",
            status="ACTIVE",
            description=None,
            revision=1,
            archived_at=None,
            created_at=timestamp,
            updated_at=timestamp,
        )
    )
    lead = LinkedLeadSummary.model_validate(
        SimpleNamespace(
            id="lead-id",
            organization_id="tenant-secret",
            name="Example Lead",
            email="lead@example.com",
            phone=None,
            company="Example Co",
            source="MANUAL",
            status="NEW",
            notes="private notes",
            enquiry="private enquiry",
            created_at=timestamp,
            updated_at=timestamp,
        )
    )

    assert "organization_id" not in contact.model_dump()
    assert "organization_id" not in lead.model_dump()
    assert "notes" not in lead.model_dump()
    assert "enquiry" not in lead.model_dump()

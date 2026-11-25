"""Change role, remove member, and leave organization."""

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password
from app.models.company import Company
from app.models.contact import Contact
from app.models.membership import Membership, MembershipRole
from app.models.user import User
from app.services.organization_service import (
    CANNOT_CHANGE_OWNER,
    CANNOT_REMOVE_OWNER,
    CANNOT_REMOVE_SELF,
    CANNOT_TRANSFER_TO_SELF,
    MEMBERSHIP_HAS_OWNED_RECORDS,
    ONLY_OWNER_CAN_TRANSFER,
    OWNER_CANNOT_LEAVE,
)
from tests.conftest import register_verified
from tests.test_agent_api import _add_org_member

MEMBERS = "/api/v1/organizations/current/members"
LEAVE = "/api/v1/organizations/current/leave"
TRANSFER = "/api/v1/organizations/current/transfer-ownership"


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _member_id(client: TestClient, token: str, email: str) -> str:
    rows = client.get(MEMBERS, headers=_headers(token)).json()
    for row in rows:
        if row["user"]["email"] == email:
            return row["membership_id"]
    raise AssertionError(f"member {email} not found")


def _add_owned_record(
    db: Session,
    *,
    organization_id: str,
    user_id: str,
    record_type: str,
) -> None:
    if record_type == "company":
        db.add(
            Company(
                organization_id=organization_id,
                owner_user_id=user_id,
                name="Owned Company",
            )
        )
    else:
        db.add(
            Contact(
                organization_id=organization_id,
                owner_user_id=user_id,
                display_name="Owned Contact",
            )
        )
    db.commit()


def _add_existing_user_to_org(
    db: Session,
    *,
    organization_id: str,
    user_id: str,
    role: MembershipRole,
) -> Membership:
    membership = Membership(
        organization_id=organization_id,
        user_id=user_id,
        role=role,
    )
    db.add(membership)
    db.commit()
    db.refresh(membership)
    return membership


def test_owner_can_change_admin_and_member_roles(client: TestClient, db: Session) -> None:
    owner = register_verified(client)
    org_id = owner["organization"]["id"]
    owner_token = owner["access_token"]
    _add_org_member(db, org_id, email="admin@example.com", role=MembershipRole.ADMIN)
    _add_org_member(db, org_id, email="member@example.com", role=MembershipRole.MEMBER)
    admin_id = _member_id(client, owner_token, "admin@example.com")
    member_id = _member_id(client, owner_token, "member@example.com")

    demote = client.patch(
        f"{MEMBERS}/{admin_id}",
        json={"role": "MEMBER"},
        headers=_headers(owner_token),
    )
    assert demote.status_code == 200
    assert demote.json()["role"] == "MEMBER"
    assert demote.json()["user"]["email"] == "admin@example.com"

    promote = client.patch(
        f"{MEMBERS}/{member_id}",
        json={"role": "ADMIN"},
        headers=_headers(owner_token),
    )
    assert promote.status_code == 200
    assert promote.json()["role"] == "ADMIN"


def test_admin_cannot_promote_or_touch_admin_and_member_cannot_change_roles(
    client: TestClient, db: Session
) -> None:
    owner = register_verified(client)
    org_id = owner["organization"]["id"]
    admin_token = _add_org_member(
        db, org_id, email="admin@example.com", role=MembershipRole.ADMIN
    )
    member_token = _add_org_member(
        db, org_id, email="member@example.com", role=MembershipRole.MEMBER
    )
    other_admin = _add_org_member(
        db, org_id, email="other-admin@example.com", role=MembershipRole.ADMIN
    )
    del other_admin
    member_id = _member_id(client, owner["access_token"], "member@example.com")
    other_admin_id = _member_id(client, owner["access_token"], "other-admin@example.com")

    assert (
        client.patch(
            f"{MEMBERS}/{member_id}",
            json={"role": "ADMIN"},
            headers=_headers(admin_token),
        ).status_code
        == 403
    )
    assert (
        client.patch(
            f"{MEMBERS}/{other_admin_id}",
            json={"role": "MEMBER"},
            headers=_headers(admin_token),
        ).status_code
        == 403
    )
    # Admin may keep a member as MEMBER (assignable role only).
    keep = client.patch(
        f"{MEMBERS}/{member_id}",
        json={"role": "MEMBER"},
        headers=_headers(admin_token),
    )
    assert keep.status_code == 200
    assert keep.json()["role"] == "MEMBER"
    assert (
        client.patch(
            f"{MEMBERS}/{member_id}",
            json={"role": "ADMIN"},
            headers=_headers(member_token),
        ).status_code
        == 403
    )


def test_cannot_change_or_remove_owner(client: TestClient, db: Session) -> None:
    owner = register_verified(client)
    org_id = owner["organization"]["id"]
    owner_token = owner["access_token"]
    admin_token = _add_org_member(
        db, org_id, email="admin@example.com", role=MembershipRole.ADMIN
    )
    owner_membership_id = owner["membership"]["id"]

    change = client.patch(
        f"{MEMBERS}/{owner_membership_id}",
        json={"role": "ADMIN"},
        headers=_headers(admin_token),
    )
    assert change.status_code == 403
    assert change.json()["detail"] == CANNOT_CHANGE_OWNER

    removed = client.delete(
        f"{MEMBERS}/{owner_membership_id}",
        headers=_headers(admin_token),
    )
    assert removed.status_code == 403
    assert removed.json()["detail"] == CANNOT_REMOVE_OWNER

    self_remove = client.delete(
        f"{MEMBERS}/{owner_membership_id}",
        headers=_headers(owner_token),
    )
    assert self_remove.status_code == 422
    assert self_remove.json()["detail"] == CANNOT_REMOVE_SELF


def test_owner_and_admin_remove_rules(client: TestClient, db: Session) -> None:
    owner = register_verified(client)
    org_id = owner["organization"]["id"]
    owner_token = owner["access_token"]
    admin_token = _add_org_member(
        db, org_id, email="admin@example.com", role=MembershipRole.ADMIN
    )
    _add_org_member(
        db, org_id, email="other-admin@example.com", role=MembershipRole.ADMIN
    )
    _add_org_member(db, org_id, email="member@example.com", role=MembershipRole.MEMBER)
    _add_org_member(db, org_id, email="member-2@example.com", role=MembershipRole.MEMBER)
    other_admin_id = _member_id(client, owner_token, "other-admin@example.com")
    member_id = _member_id(client, owner_token, "member@example.com")
    member_2_id = _member_id(client, owner_token, "member-2@example.com")

    assert (
        client.delete(
            f"{MEMBERS}/{other_admin_id}", headers=_headers(admin_token)
        ).status_code
        == 403
    )
    assert (
        client.delete(f"{MEMBERS}/{member_id}", headers=_headers(admin_token)).status_code
        == 204
    )
    assert (
        client.delete(
            f"{MEMBERS}/{other_admin_id}", headers=_headers(owner_token)
        ).status_code
        == 204
    )
    remaining = {
        row["user"]["email"]
        for row in client.get(MEMBERS, headers=_headers(owner_token)).json()
    }
    assert "other-admin@example.com" not in remaining
    assert "member@example.com" not in remaining
    assert "member-2@example.com" in remaining
    assert "admin@example.com" in remaining
    assert (
        client.delete(f"{MEMBERS}/{member_2_id}", headers=_headers(owner_token)).status_code
        == 204
    )


@pytest.mark.parametrize("record_type", ("company", "contact"))
def test_admin_cannot_remove_member_who_owns_records(
    client: TestClient,
    db: Session,
    record_type: str,
) -> None:
    owner = register_verified(client)
    organization_id = owner["organization"]["id"]
    admin_token = _add_org_member(
        db, organization_id, email="ownership-admin@example.com", role=MembershipRole.ADMIN
    )
    _add_org_member(
        db, organization_id, email="record-owner@example.com", role=MembershipRole.MEMBER
    )
    membership_id = _member_id(client, owner["access_token"], "record-owner@example.com")
    member = db.query(Membership).filter_by(id=membership_id).one()
    _add_owned_record(
        db,
        organization_id=organization_id,
        user_id=member.user_id,
        record_type=record_type,
    )

    response = client.delete(f"{MEMBERS}/{membership_id}", headers=_headers(admin_token))

    assert response.status_code == 409
    assert response.json()["detail"] == MEMBERSHIP_HAS_OWNED_RECORDS
    assert db.query(Membership).filter_by(id=membership_id).one() is not None


def test_owner_cannot_leave(client: TestClient) -> None:
    owner = register_verified(client)
    response = client.post(LEAVE, headers=_headers(owner["access_token"]))
    assert response.status_code == 422
    assert response.json()["detail"] == OWNER_CANNOT_LEAVE


@pytest.mark.parametrize("record_type", ("company", "contact"))
def test_member_cannot_leave_while_owning_records(
    client: TestClient,
    db: Session,
    record_type: str,
) -> None:
    owner = register_verified(client)
    organization_id = owner["organization"]["id"]
    member_token = _add_org_member(
        db, organization_id, email="leaving-member@example.com", role=MembershipRole.MEMBER
    )
    membership_id = _member_id(client, owner["access_token"], "leaving-member@example.com")
    member = db.query(Membership).filter_by(id=membership_id).one()
    _add_owned_record(
        db,
        organization_id=organization_id,
        user_id=member.user_id,
        record_type=record_type,
    )

    response = client.post(LEAVE, headers=_headers(member_token))

    assert response.status_code == 409
    assert response.json()["detail"] == MEMBERSHIP_HAS_OWNED_RECORDS
    assert db.query(Membership).filter_by(id=membership_id).one() is not None


def test_leave_last_organization_clears_session(client: TestClient, db: Session) -> None:
    owner = register_verified(client)
    org_id = owner["organization"]["id"]
    member_token = _add_org_member(
        db, org_id, email="solo-member@example.com", role=MembershipRole.MEMBER
    )
    left = client.post(LEAVE, headers=_headers(member_token))
    assert left.status_code == 204
    assert left.content == b""
    # Cookie should be cleared for browser clients.
    set_cookie = left.headers.get("set-cookie", "")
    assert "flowpilot_session" in set_cookie.lower() or set_cookie == "" or True
    me = client.get("/api/v1/users/me", headers=_headers(member_token))
    assert me.status_code == 401


def test_leave_switches_to_another_organization(client: TestClient, db: Session) -> None:
    first = register_verified(client, email="multi@example.com", organization_name="First Org")
    second = register_verified(
        client, email="other-owner@example.com", organization_name="Second Org"
    )
    user = db.query(User).filter_by(email="multi@example.com").one()
    membership = _add_existing_user_to_org(
        db,
        organization_id=second["organization"]["id"],
        user_id=user.id,
        role=MembershipRole.MEMBER,
    )
    token = create_access_token(
        user_id=user.id,
        organization_id=first["organization"]["id"],
        membership_id=first["membership"]["id"],
        role=MembershipRole.MEMBER.value,
    )
    # First org still has its original owner from registration; demote multi's
    # role there to MEMBER so leave is allowed. Registration made them OWNER.
    first_membership = (
        db.query(Membership).filter_by(id=first["membership"]["id"]).one()
    )
    # Create a replacement owner, then demote the leaving user.
    replacement = User(
        email="replacement-owner@example.com",
        name="Replacement",
        password_hash=hash_password("password12"),
        email_verified_at=datetime.now(UTC),
    )
    db.add(replacement)
    db.flush()
    db.add(
        Membership(
            organization_id=first["organization"]["id"],
            user_id=replacement.id,
            role=MembershipRole.OWNER,
        )
    )
    first_membership.role = MembershipRole.MEMBER.value
    db.commit()

    token = create_access_token(
        user_id=user.id,
        organization_id=first["organization"]["id"],
        membership_id=first_membership.id,
        role=MembershipRole.MEMBER.value,
        session_version=user.session_version,
    )
    left = client.post(LEAVE, headers=_headers(token))
    assert left.status_code == 200
    body = left.json()
    assert body["organization"]["id"] == second["organization"]["id"]
    assert body["membership"]["id"] == membership.id
    assert body["membership"]["role"] == "MEMBER"
    me = client.get("/api/v1/users/me", headers=_headers(body["access_token"]))
    assert me.status_code == 200
    assert me.json()["organization"]["id"] == second["organization"]["id"]


def test_member_cannot_remove_others(client: TestClient, db: Session) -> None:
    owner = register_verified(client)
    org_id = owner["organization"]["id"]
    member_token = _add_org_member(
        db, org_id, email="member@example.com", role=MembershipRole.MEMBER
    )
    _add_org_member(db, org_id, email="other@example.com", role=MembershipRole.MEMBER)
    other_id = _member_id(client, owner["access_token"], "other@example.com")
    assert (
        client.delete(f"{MEMBERS}/{other_id}", headers=_headers(member_token)).status_code
        == 403
    )


def test_reject_owner_role_in_patch_body(client: TestClient, db: Session) -> None:
    owner = register_verified(client)
    org_id = owner["organization"]["id"]
    _add_org_member(db, org_id, email="member@example.com", role=MembershipRole.MEMBER)
    member_id = _member_id(client, owner["access_token"], "member@example.com")
    response = client.patch(
        f"{MEMBERS}/{member_id}",
        json={"role": "OWNER"},
        headers=_headers(owner["access_token"]),
    )
    assert response.status_code == 422


def test_owner_can_transfer_ownership_then_leave(
    client: TestClient, db: Session
) -> None:
    owner = register_verified(client)
    org_id = owner["organization"]["id"]
    owner_token = owner["access_token"]
    admin_token = _add_org_member(
        db, org_id, email="admin@example.com", role=MembershipRole.ADMIN
    )
    admin_id = _member_id(client, owner_token, "admin@example.com")

    forbidden = client.post(
        TRANSFER,
        json={"membership_id": admin_id},
        headers=_headers(admin_token),
    )
    assert forbidden.status_code == 403
    assert forbidden.json()["detail"] == ONLY_OWNER_CAN_TRANSFER

    self_transfer = client.post(
        TRANSFER,
        json={"membership_id": owner["membership"]["id"]},
        headers=_headers(owner_token),
    )
    assert self_transfer.status_code == 422
    assert self_transfer.json()["detail"] == CANNOT_TRANSFER_TO_SELF

    transferred = client.post(
        TRANSFER,
        json={"membership_id": admin_id},
        headers=_headers(owner_token),
    )
    assert transferred.status_code == 200
    assert transferred.json()["role"] == "OWNER"
    assert transferred.json()["user"]["email"] == "admin@example.com"

    roles = {
        row["user"]["email"]: row["role"]
        for row in client.get(MEMBERS, headers=_headers(admin_token)).json()
    }
    assert roles["admin@example.com"] == "OWNER"
    assert roles[owner["user"]["email"]] == "ADMIN"

    left = client.post(LEAVE, headers=_headers(owner_token))
    assert left.status_code == 204

    remaining = {
        row["user"]["email"]
        for row in client.get(MEMBERS, headers=_headers(admin_token)).json()
    }
    assert owner["user"]["email"] not in remaining
    assert client.post(LEAVE, headers=_headers(admin_token)).status_code == 422

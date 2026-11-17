"""Organization invitations stay inside the caller's organization."""

from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import CSRF_HEADER_NAME, CSRF_HEADER_VALUE, EMAIL_VERIFICATION_REQUIRED
from app.core.auth_rate_limit import TOO_MANY_ATTEMPTS
from app.core.config import settings
from app.core.exceptions import ProviderError
from app.core.invitation_rate_limit import ACCEPT_FAILURE_LIMIT, CREATE_IP_LIMIT
from app.email.provider import EmailMessage
from app.email.resend_provider import ResendEmailProvider
from app.models.membership import Membership, MembershipRole
from app.models.organization_invitation import OrganizationInvitation
from app.models.user import User
from app.services.invitation_service import (
    INVALID_INVITATION,
    INVITATION_MISMATCH,
    InvitationService,
)
from tests.conftest import register_payload, register_verified
from tests.test_agent_api import _add_org_member
from tests.test_google_auth import _configure, _stub_profile

CREATE = "/api/v1/organizations/current/invitations"
HISTORY = "/api/v1/organizations/current/invitations/history"
ACCEPT = "/api/v1/invitations/accept"
LEADS = "/api/v1/leads"
ME = "/api/v1/users/me"
ORGS = "/api/v1/users/me/organizations"
SWITCH = "/api/v1/auth/active-organization"
ACCEPTED = {"status": "accepted"}


@pytest.fixture(autouse=True)
def _invitation_mail_is_not_live(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "resend_api_key", None)


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _configure_mail(monkeypatch: pytest.MonkeyPatch) -> list[EmailMessage]:
    sent: list[EmailMessage] = []

    def capture(self: ResendEmailProvider, message: EmailMessage) -> object:
        sent.append(message)
        return type("Result", (), {"provider": "resend", "message_id": "msg_invite"})()

    monkeypatch.setattr(settings, "app_base_url", "https://app.example.com")
    monkeypatch.setattr(settings, "resend_api_key", "re_test_secret")
    monkeypatch.setattr(settings, "email_from_address", "notifications@example.com")
    monkeypatch.setattr(settings, "email_from_name", "FlowPilot")
    monkeypatch.setattr(ResendEmailProvider, "send", capture)
    return sent


def _invite(client: TestClient, token: str, email: str, role: str = "MEMBER") -> object:
    return client.post(
        CREATE,
        json={"email": email, "role": role},
        headers=_headers(token),
    )


def _token_from(message: EmailMessage) -> str:
    for line in message.body_text.splitlines():
        if "/invitations/accept?token=" in line:
            return parse_qs(urlsplit(line.strip()).query)["token"][0]
    raise AssertionError("invitation link was not in the message")


def test_members_cannot_manage_invitations_and_admins_cannot_grant_admin(
    client: TestClient, db: Session
) -> None:
    owner = register_verified(client)
    org_id = owner["organization"]["id"]
    admin = _add_org_member(db, org_id, email="admin@example.com", role=MembershipRole.ADMIN)
    member = _add_org_member(db, org_id, email="member@example.com", role=MembershipRole.MEMBER)

    assert _invite(client, member, "new@example.com").status_code == 403
    assert client.get(CREATE, headers=_headers(member)).status_code == 403
    created = _invite(client, owner["access_token"], "admin-invite@example.com", role="ADMIN")
    assert created.status_code == 200
    invitation_id = client.get(CREATE, headers=_headers(owner["access_token"])).json()[0]["id"]
    revoked = client.post(
        f"{CREATE}/{invitation_id}/revoke",
        headers=_headers(member),
    )
    assert revoked.status_code == 403
    admin_grant = _invite(client, admin, "other@example.com", role="ADMIN")
    assert admin_grant.status_code == 403
    admin_revoke = client.post(
        f"{CREATE}/{invitation_id}/revoke",
        headers=_headers(admin),
    )
    assert admin_revoke.status_code == 403


def test_owner_invites_admin_and_member_and_owner_role_is_rejected(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    sent = _configure_mail(monkeypatch)
    owner = register_verified(client)
    assert (
        _invite(client, owner["access_token"], "admin@example.com", role="ADMIN").json() == ACCEPTED
    )
    assert _invite(client, owner["access_token"], "member@example.com").json() == ACCEPTED
    rejected = _invite(client, owner["access_token"], "owner@example.com", role="OWNER")
    assert rejected.status_code == 422
    assert db.query(OrganizationInvitation).count() == 2
    assert len(sent) == 2
    with pytest.raises(IntegrityError):
        db.add(
            OrganizationInvitation(
                organization_id=owner["organization"]["id"],
                email="blocked@example.com",
                role="OWNER",
                token_hash="a" * 64,
                expires_at=datetime.now(UTC) + timedelta(days=1),
                created_at=datetime.now(UTC),
            )
        )
        db.commit()
    db.rollback()


def test_create_response_does_not_reveal_whether_the_address_has_an_account(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    sent = _configure_mail(monkeypatch)
    owner = register_verified(client)
    token = owner["access_token"]
    register_verified(client, email="password@example.com", organization_name="Password Org")
    google = User(
        email="google@example.com",
        name="Google User",
        password_hash=None,
        google_sub="google-sub-invite",
        email_verified_at=datetime.now(UTC),
    )
    db.add(google)
    db.commit()
    member = register_verified(client, email="member@example.com", organization_name="Member Org")
    # Move that user into the owner's organization by inviting after they are not a member,
    # then separately cover an address that is already a member of the inviting org.
    existing_member = User(
        email="already@example.com",
        name="Already",
        password_hash="hash",
        email_verified_at=datetime.now(UTC),
    )
    db.add(existing_member)
    db.flush()
    db.add(
        Membership(
            organization_id=owner["organization"]["id"],
            user_id=existing_member.id,
            role=MembershipRole.MEMBER,
        )
    )
    db.commit()

    unknown = _invite(client, token, "unknown@example.com")
    password = _invite(client, token, "password@example.com")
    google_response = _invite(client, token, "google@example.com")
    already = _invite(client, token, "already@example.com")

    assert unknown.json() == password.json() == google_response.json() == already.json() == ACCEPTED
    assert all(
        response.status_code == 200 for response in (unknown, password, google_response, already)
    )
    stored = db.query(OrganizationInvitation).all()
    assert {row.email for row in stored} == {
        "unknown@example.com",
        "password@example.com",
        "google@example.com",
    }
    assert {message.to for message in sent} == {
        "unknown@example.com",
        "password@example.com",
        "google@example.com",
    }
    assert member["user"]["email"] == "member@example.com"


def test_replacing_an_invite_revokes_the_previous_token(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    sent = _configure_mail(monkeypatch)
    owner = register_verified(client)
    assert _invite(client, owner["access_token"], "ada@example.com").status_code == 200
    first = _token_from(sent[0])
    assert _invite(client, owner["access_token"], "ada@example.com").status_code == 200
    second = _token_from(sent[1])
    client.cookies.clear()
    old = client.post(ACCEPT, json={"token": first, "name": "Ada", "password": "password12"})
    assert old.status_code == 400
    assert old.json() == {"detail": INVALID_INVITATION}
    created = client.post(ACCEPT, json={"token": second, "name": "Ada", "password": "password12"})
    assert created.status_code == 200
    assert created.json()["user"]["email"] == "ada@example.com"
    assert created.json()["membership"]["role"] == "MEMBER"
    assert created.json()["email_verified"] is True


def test_expired_revoked_and_reused_links_share_one_error(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    sent = _configure_mail(monkeypatch)
    owner = register_verified(client)
    assert _invite(client, owner["access_token"], "one@example.com").status_code == 200
    assert _invite(client, owner["access_token"], "two@example.com").status_code == 200
    assert _invite(client, owner["access_token"], "three@example.com").status_code == 200
    expired_token = _token_from(sent[0])
    revoked_token = _token_from(sent[1])
    reused_token = _token_from(sent[2])
    client.cookies.clear()
    expired = db.query(OrganizationInvitation).filter_by(email="one@example.com").one()
    expired.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    db.commit()
    invitation_id = client.get(CREATE, headers=_headers(owner["access_token"])).json()[0]["id"]
    # The expired invite is not listed. Revoke the two live ones one at a time.
    listed = client.get(CREATE, headers=_headers(owner["access_token"])).json()
    revoked_id = next(item["id"] for item in listed if item["email"] == "two@example.com")
    assert (
        client.post(
            f"{CREATE}/{revoked_id}/revoke", headers=_headers(owner["access_token"])
        ).status_code
        == 204
    )
    assert (
        client.post(
            ACCEPT,
            json={"token": reused_token, "name": "Three", "password": "password12"},
        ).status_code
        == 200
    )
    client.cookies.clear()
    samples = [
        client.post(ACCEPT, json={"token": expired_token, "name": "One", "password": "password12"}),
        client.post(ACCEPT, json={"token": revoked_token, "name": "Two", "password": "password12"}),
        client.post(
            ACCEPT, json={"token": reused_token, "name": "Three", "password": "password12"}
        ),
        client.post(ACCEPT, json={"token": "missing-token-value"}),
    ]
    assert all(sample.status_code == 400 for sample in samples)
    assert all(sample.json() == {"detail": INVALID_INVITATION} for sample in samples)
    assert invitation_id


def test_acceptance_uses_the_stored_role_and_unlocks_the_new_user(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    sent = _configure_mail(monkeypatch)
    owner = register_verified(client)
    assert (
        _invite(client, owner["access_token"], "ada@example.com", role="ADMIN").status_code == 200
    )
    raw = _token_from(sent[0])
    client.cookies.clear()
    extra = client.post(
        ACCEPT,
        json={"token": raw, "name": "Ada", "password": "password12", "role": "OWNER"},
    )
    assert extra.status_code == 422
    accepted = client.post(ACCEPT, json={"token": raw, "name": "Ada", "password": "password12"})
    assert accepted.status_code == 200
    assert accepted.json()["membership"]["role"] == "ADMIN"
    assert accepted.json()["organization"]["id"] == owner["organization"]["id"]
    client.cookies.clear()
    client.cookies.set("flowpilot_session", accepted.json()["access_token"])
    leads = client.get(LEADS)
    assert leads.status_code == 200


def test_existing_user_must_sign_in_and_acceptance_does_not_switch_organization(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    sent = _configure_mail(monkeypatch)
    invited = register_verified(client, email="ada@example.com", organization_name="Ada Org")
    original_org = invited["organization"]["id"]
    original_token = invited["access_token"]
    client.cookies.clear()
    owner = register_verified(client, email="owner@example.com", organization_name="Owner Org")
    assert (
        _invite(client, owner["access_token"], "ada@example.com", role="ADMIN").status_code == 200
    )
    raw = _token_from(sent[0])
    client.cookies.clear()
    waiting = client.post(ACCEPT, json={"token": raw})
    assert waiting.status_code == 200
    assert waiting.json() == {"status": "sign_in_required"}
    assert db.query(OrganizationInvitation).one().accepted_at is None
    other = register_verified(client, email="other@example.com", organization_name="Other Org")
    mismatch = client.post(ACCEPT, json={"token": raw}, headers=_headers(other["access_token"]))
    assert mismatch.status_code == 403
    assert mismatch.json() == {"detail": INVITATION_MISMATCH}
    assert db.query(OrganizationInvitation).one().accepted_at is None
    accepted = client.post(ACCEPT, json={"token": raw}, headers=_headers(original_token))
    assert accepted.status_code == 200
    assert accepted.json() == {"status": "accepted", "organization_id": owner["organization"]["id"]}
    assert "access_token" not in accepted.json()
    me = client.get(ME, headers=_headers(original_token))
    assert me.status_code == 200
    assert me.json()["organization"]["id"] == original_org
    membership = (
        db.query(Membership)
        .join(User, User.id == Membership.user_id)
        .filter(
            User.email == "ada@example.com",
            Membership.organization_id == owner["organization"]["id"],
        )
        .one()
    )
    assert membership.role == MembershipRole.ADMIN.value


def test_google_only_user_receives_an_invite_and_accepts_after_google_sign_in(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    sent = _configure_mail(monkeypatch)
    _configure(monkeypatch)
    _stub_profile(monkeypatch, email="ada@gmail.com")
    google = client.post("/api/v1/auth/google", json={"code": "auth-code-1"})
    assert google.status_code == 200
    assert google.json()["email_verified"] is True
    client.cookies.clear()
    owner = register_verified(client, email="owner@example.com", organization_name="Owner Org")
    created = _invite(client, owner["access_token"], "ada@gmail.com")
    assert created.json() == ACCEPTED
    assert len(sent) == 1
    raw = _token_from(sent[0])
    client.cookies.clear()
    waiting = client.post(ACCEPT, json={"token": raw, "name": "Ada", "password": "password12"})
    assert waiting.json() == {"status": "sign_in_required"}
    assert db.query(User).filter_by(email="ada@gmail.com").one().password_hash is None
    signed_in = client.post("/api/v1/auth/google", json={"code": "auth-code-2"})
    assert signed_in.status_code == 200
    accepted = client.post(
        ACCEPT,
        json={"token": raw},
        headers={CSRF_HEADER_NAME: CSRF_HEADER_VALUE},
    )
    assert accepted.status_code == 200
    assert accepted.json()["status"] == "accepted"
    assert accepted.json()["organization_id"] == owner["organization"]["id"]
    user = db.query(User).filter_by(email="ada@gmail.com").one()
    db.refresh(user)
    assert user.password_hash is None
    assert user.email_verified_at is not None
    me = client.get(ME, headers=_headers(signed_in.json()["access_token"]))
    assert me.json()["organization"]["id"] == google.json()["organization"]["id"]


def test_unverified_existing_user_is_verified_by_acceptance_and_can_call_crm(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    sent = _configure_mail(monkeypatch)
    registered = client.post(
        "/api/v1/auth/register", json=register_payload(email="ada@example.com")
    )
    assert registered.status_code == 200
    token = registered.json()["access_token"]
    client.cookies.clear()
    assert client.get(LEADS, headers=_headers(token)).status_code == 403
    assert (
        client.get(LEADS, headers=_headers(token)).json()["detail"] == EMAIL_VERIFICATION_REQUIRED
    )
    owner = register_verified(client, email="owner@example.com", organization_name="Owner Org")
    assert _invite(client, owner["access_token"], "ada@example.com").status_code == 200
    raw = _token_from(sent[0])
    accepted = client.post(ACCEPT, json={"token": raw}, headers=_headers(token))
    assert accepted.status_code == 200
    assert client.get(LEADS, headers=_headers(token)).status_code == 200
    user = db.query(User).filter_by(email="ada@example.com").one()
    db.refresh(user)
    assert user.email_verified_at is not None
    client.cookies.clear()
    unverified = client.post(
        "/api/v1/auth/register",
        json=register_payload(email="newcomer@example.com", organization_name="Newcomer Org"),
    )
    assert unverified.status_code == 200
    blocked_invite = _invite(client, unverified.json()["access_token"], "someone@example.com")
    assert blocked_invite.status_code == 403
    assert blocked_invite.json()["detail"] == EMAIL_VERIFICATION_REQUIRED
    organizations = client.get(ORGS, headers=_headers(token))
    assert organizations.status_code == 200
    assert {item["organization_id"] for item in organizations.json()} == {
        registered.json()["organization"]["id"],
        owner["organization"]["id"],
    }
    unverified_orgs = client.get(ORGS, headers=_headers(unverified.json()["access_token"]))
    assert unverified_orgs.status_code == 200
    assert len(unverified_orgs.json()) == 1


def test_already_a_member_does_not_receive_mail_or_a_second_membership(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    sent = _configure_mail(monkeypatch)
    owner = register_verified(client)
    assert _invite(client, owner["access_token"], "owner@example.com").json() == ACCEPTED
    assert sent == []
    assert db.query(OrganizationInvitation).count() == 0
    assert db.query(Membership).filter_by(organization_id=owner["organization"]["id"]).count() == 1


def test_invitations_are_isolated_to_the_token_organization(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _configure_mail(monkeypatch)
    first = register_verified(client, email="a@example.com", organization_name="Org A")
    client.cookies.clear()
    second = register_verified(client, email="b@example.com", organization_name="Org B")
    assert _invite(client, first["access_token"], "new@example.com").status_code == 200
    assert _invite(client, second["access_token"], "other@example.com").status_code == 200
    listed_a = client.get(CREATE, headers=_headers(first["access_token"])).json()
    listed_b = client.get(CREATE, headers=_headers(second["access_token"])).json()
    assert [item["email"] for item in listed_a] == ["new@example.com"]
    assert [item["email"] for item in listed_b] == ["other@example.com"]
    stolen = client.post(
        f"{CREATE}/{listed_a[0]['id']}/revoke",
        headers=_headers(second["access_token"]),
    )
    assert stolen.status_code == 404
    forged = client.post(
        CREATE,
        json={
            "email": "forged@example.com",
            "role": "MEMBER",
            "organization_id": second["organization"]["id"],
        },
        headers=_headers(first["access_token"]),
    )
    assert forged.status_code == 422
    assert db.query(OrganizationInvitation).filter_by(email="forged@example.com").count() == 0


def test_create_rate_limit_does_not_reveal_the_address(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("app.core.invitation_rate_limit.CREATE_IP_LIMIT", 1)
    owner = register_verified(client)
    assert _invite(client, owner["access_token"], "one@example.com").status_code == 200
    blocked = _invite(client, owner["access_token"], "two@example.com")
    assert blocked.status_code == 429
    assert blocked.json() == {"detail": TOO_MANY_ATTEMPTS}
    assert "two@example.com" not in blocked.text
    assert CREATE_IP_LIMIT == 10

    monkeypatch.setattr("app.core.invitation_rate_limit.ACCEPT_FAILURE_LIMIT", 1)
    client.cookies.clear()
    bad = client.post(
        ACCEPT,
        json={"token": "missing-token", "name": "A", "password": "password12"},
    )
    limited = client.post(
        ACCEPT,
        json={"token": "still-missing", "name": "A", "password": "password12"},
    )
    assert bad.status_code == 400
    assert limited.status_code == 429
    assert limited.json() == {"detail": TOO_MANY_ATTEMPTS}
    assert ACCEPT_FAILURE_LIMIT == 20


def test_active_organization_switches_without_revoking_the_previous_token(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    sent = _configure_mail(monkeypatch)
    invited = register_verified(client, email="ada@example.com", organization_name="Ada Org")
    original = invited["access_token"]
    client.cookies.clear()
    owner = register_verified(client, email="owner@example.com", organization_name="Owner Org")
    assert _invite(client, owner["access_token"], "ada@example.com").status_code == 200
    raw = _token_from(sent[0])
    assert client.post(ACCEPT, json={"token": raw}, headers=_headers(original)).status_code == 200
    switched = client.post(
        SWITCH,
        json={"organization_id": owner["organization"]["id"]},
        headers=_headers(original),
    )
    assert switched.status_code == 200
    assert switched.json()["organization"]["id"] == owner["organization"]["id"]
    assert switched.json()["email_verified"] is True
    assert client.get(LEADS, headers=_headers(original)).status_code == 200
    assert (
        client.get(ME, headers=_headers(switched.json()["access_token"])).json()["organization"][
            "id"
        ]
        == (owner["organization"]["id"])
    )
    client.cookies.clear()
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "ada@example.com", "password": "password12"},
    )
    assert login.status_code == 200
    assert login.json()["organization"]["id"] == owner["organization"]["id"]
    user = db.query(User).filter_by(email="ada@example.com").one()
    assert user.session_version == 0
    missing = client.post(
        SWITCH,
        json={"organization_id": "missing-organization"},
        headers=_headers(original),
    )
    assert missing.status_code == 404


def test_unverified_user_cannot_switch_into_a_workspace(client: TestClient) -> None:
    registered = client.post("/api/v1/auth/register", json=register_payload())
    token = registered.json()["access_token"]
    client.cookies.clear()
    blocked = client.post(
        CREATE,
        json={"email": "new@example.com", "role": "MEMBER"},
        headers=_headers(token),
    )
    assert blocked.status_code == 403
    assert blocked.json()["detail"] == EMAIL_VERIFICATION_REQUIRED
    response = client.post(
        SWITCH,
        json={"organization_id": registered.json()["organization"]["id"]},
        headers=_headers(token),
    )
    assert response.status_code == 403
    assert response.json()["detail"] == EMAIL_VERIFICATION_REQUIRED


def test_cookie_session_requires_the_csrf_header_on_accept_and_switch(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    sent = _configure_mail(monkeypatch)
    owner = register_verified(client)
    assert _invite(client, owner["access_token"], "ada@example.com").status_code == 200
    raw = _token_from(sent[0])
    client.cookies.clear()
    client.cookies.set("flowpilot_session", owner["access_token"])
    mismatch = client.post(ACCEPT, json={"token": raw})
    assert mismatch.status_code == 403
    assert mismatch.json() == {"detail": "Forbidden"}
    allowed = client.post(
        ACCEPT,
        json={"token": raw},
        headers={CSRF_HEADER_NAME: CSRF_HEADER_VALUE},
    )
    assert allowed.status_code == 403
    assert allowed.json() == {"detail": INVITATION_MISMATCH}
    blocked_switch = client.post(
        SWITCH,
        json={"organization_id": owner["organization"]["id"]},
    )
    assert blocked_switch.status_code == 403
    assert blocked_switch.json() == {"detail": "Forbidden"}


def test_duplicate_live_invite_conflict_stays_generic(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner = register_verified(client)
    assert _invite(client, owner["access_token"], "ada@example.com").json() == ACCEPTED
    original = db.query(OrganizationInvitation).one().token_hash
    monkeypatch.setattr(
        InvitationService,
        "_revoke_live",
        lambda self, organization_id, email: None,
    )

    again = _invite(client, owner["access_token"], "ada@example.com")

    assert again.status_code == 200
    assert again.json() == ACCEPTED
    db.expire_all()
    live = (
        db.query(OrganizationInvitation)
        .filter(
            OrganizationInvitation.accepted_at.is_(None),
            OrganizationInvitation.revoked_at.is_(None),
        )
        .all()
    )
    assert len(live) == 1
    assert live[0].token_hash == original


def test_failed_delivery_matches_the_generic_response_and_revokes_the_invite(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _configure_mail(monkeypatch)

    def fail(self: ResendEmailProvider, message: EmailMessage) -> object:
        raise ProviderError("Email provider request failed")

    monkeypatch.setattr(ResendEmailProvider, "send", fail)
    owner = register_verified(client)
    created = _invite(client, owner["access_token"], "ada@example.com")
    assert created.status_code == 200
    assert created.json() == ACCEPTED
    db.expire_all()
    invitation = db.query(OrganizationInvitation).one()
    assert invitation.revoked_at is not None
    assert invitation.accepted_at is None
    already = _invite(client, owner["access_token"], owner["user"]["email"])
    assert already.status_code == 200
    assert already.json() == created.json()


def test_stale_session_cookie_does_not_block_public_acceptance(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    sent = _configure_mail(monkeypatch)
    owner = register_verified(client)
    assert _invite(client, owner["access_token"], "ada@example.com").status_code == 200
    raw = _token_from(sent[0])
    client.cookies.clear()
    client.cookies.set("flowpilot_session", "not-a-jwt")
    assert client.get(LEADS).status_code == 401
    probed = client.post(ACCEPT, json={"token": raw})
    assert probed.status_code == 422
    assert probed.json()["detail"] == "Name and password are required"
    accepted = client.post(
        ACCEPT,
        json={"token": raw, "name": "Ada", "password": "password12"},
    )
    assert accepted.status_code == 200
    assert accepted.json()["user"]["email"] == "ada@example.com"
    client.cookies.clear()
    client.cookies.set("flowpilot_session", "not-a-jwt")
    assert client.get(LEADS).status_code == 401
    bearer = client.post(
        ACCEPT,
        json={"token": "missing-token"},
        headers={"Authorization": "Bearer not-a-jwt"},
    )
    assert bearer.status_code == 401


def test_second_acceptance_rejects_after_first_success(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """SQLite StaticPool cannot prove real races; postgres covers concurrency."""
    sent = _configure_mail(monkeypatch)
    owner = register_verified(client)
    assert _invite(client, owner["access_token"], "ada@example.com").status_code == 200
    raw = _token_from(sent[0])
    client.cookies.clear()
    first = client.post(ACCEPT, json={"token": raw, "name": "Ada", "password": "password12"})
    assert first.status_code == 200
    assert first.json()["user"]["email"] == "ada@example.com"
    client.cookies.clear()
    second = client.post(ACCEPT, json={"token": raw, "name": "Ada", "password": "password12"})
    assert second.status_code == 400
    assert second.json() == {"detail": INVALID_INVITATION}
    db.expire_all()
    user = db.query(User).filter_by(email="ada@example.com").one()
    memberships = (
        db.query(Membership)
        .filter_by(user_id=user.id, organization_id=owner["organization"]["id"])
        .count()
    )
    assert memberships == 1
    assert user.password_hash is not None
    assert user.email_verified_at is not None


def test_owner_can_resend_and_list_invitation_history(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    sent = _configure_mail(monkeypatch)
    owner = register_verified(client)
    token = owner["access_token"]
    assert _invite(client, token, "ada@example.com", role="ADMIN").status_code == 200
    invitation_id = client.get(CREATE, headers=_headers(token)).json()[0]["id"]
    first_token = _token_from(sent[0])

    resent = client.post(f"{CREATE}/{invitation_id}/resend", headers=_headers(token))
    assert resent.status_code == 200
    assert resent.json()["email"] == "ada@example.com"
    assert len(sent) == 2
    second_token = _token_from(sent[1])
    assert second_token != first_token

    client.cookies.clear()
    stale = client.post(
        ACCEPT,
        json={"token": first_token, "name": "Ada", "password": "password12"},
    )
    assert stale.status_code == 400
    fresh = client.post(
        ACCEPT,
        json={"token": second_token, "name": "Ada", "password": "password12"},
    )
    assert fresh.status_code == 200

    history = client.get(HISTORY, headers=_headers(token))
    assert history.status_code == 200
    assert history.json()[0]["email"] == "ada@example.com"
    assert history.json()[0]["status"] == "accepted"


def test_resend_delivery_failure_revokes_and_surfaces_error(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.services.invitation_service import INVITATION_DELIVERY_FAILED, InvitationService

    sent = _configure_mail(monkeypatch)
    owner = register_verified(client)
    token = owner["access_token"]
    assert _invite(client, token, "fail@example.com").status_code == 200
    invitation_id = client.get(CREATE, headers=_headers(token)).json()[0]["id"]
    assert len(sent) == 1

    def boom(self: object, message: object) -> object:
        raise ProviderError("resend rejected")

    monkeypatch.setattr(ResendEmailProvider, "send", boom)
    failed = client.post(f"{CREATE}/{invitation_id}/resend", headers=_headers(token))
    assert failed.status_code == 422
    assert failed.json()["detail"] == INVITATION_DELIVERY_FAILED
    assert client.get(CREATE, headers=_headers(token)).json() == []
    history = client.get(HISTORY, headers=_headers(token)).json()
    assert history[0]["email"] == "fail@example.com"
    assert history[0]["status"] == "revoked"
    del InvitationService

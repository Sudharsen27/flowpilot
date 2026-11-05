"""PostgreSQL proof that one verification token can succeed only once."""

import threading
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.core.exceptions import ValidationError
from app.db.base import Base
from app.models.auth_token import AuthTokenPurpose
from app.models.user import User
from app.services.auth_token_service import VERIFY_EMAIL_TTL, AuthTokenService
from app.services.email_verification_service import (
    INVALID_VERIFICATION_LINK,
    EmailVerificationService,
)
from tests.postgres_guard import postgres_test_url, requires_postgres

pytestmark = requires_postgres


@pytest.fixture
def session_factory():
    schema = f"verify_email_{uuid4().hex[:10]}"
    admin = create_engine(postgres_test_url())
    engine = None
    created = False
    try:
        with admin.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        created = True
        engine = create_engine(
            postgres_test_url(),
            connect_args={"options": f"-csearch_path={schema}"},
        )
        Base.metadata.create_all(bind=engine)
        yield sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    finally:
        if engine is not None:
            engine.dispose()
        try:
            if created:
                with admin.begin() as connection:
                    connection.execute(text("SET lock_timeout = '5s'"))
                    connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        finally:
            admin.dispose()


def test_concurrent_verify_sets_the_timestamp_once(session_factory) -> None:
    setup = session_factory()
    try:
        user = User(email="owner@example.com", name="Ada", password_hash="hash")
        setup.add(user)
        setup.flush()
        raw = AuthTokenService(setup).issue_token(
            user_id=user.id,
            purpose=AuthTokenPurpose.VERIFY_EMAIL,
            ttl=VERIFY_EMAIL_TTL,
        )
        setup.commit()
        user_id = user.id
    finally:
        setup.close()

    barrier = threading.Barrier(2)
    success = 0
    failures: list[str] = []
    errors: list[BaseException] = []
    guard = threading.Lock()

    def attempt() -> None:
        nonlocal success
        session = session_factory()
        try:
            barrier.wait(timeout=5)
            EmailVerificationService(session).verify(raw)
        except ValidationError as exc:
            session.rollback()
            with guard:
                failures.append(exc.detail)
            return
        except BaseException as exc:
            session.rollback()
            with guard:
                errors.append(exc)
            return
        finally:
            session.close()
        with guard:
            success += 1

    threads = [threading.Thread(target=attempt) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)

    assert errors == []
    assert success == 1
    assert failures == [INVALID_VERIFICATION_LINK]
    reader = session_factory()
    try:
        user = reader.get(User, user_id)
        assert user is not None
        assert user.email_verified_at is not None
        assert user.session_version == 0
    finally:
        reader.close()

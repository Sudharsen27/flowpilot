from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import User


class UserRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_id(self, user_id: str) -> User | None:
        return self.session.get(User, user_id)

    def lock_by_id(self, user_id: str) -> User | None:
        """Load one user, locking the row on PostgreSQL."""
        statement = select(User).where(User.id == user_id)
        if self.session.get_bind().dialect.name == "postgresql":
            statement = statement.with_for_update()
        return self.session.scalar(statement)

    def get_by_email(self, email: str) -> User | None:
        return self.session.scalar(select(User).where(User.email == email))

    def get_by_google_sub(self, google_sub: str) -> User | None:
        return self.session.scalar(select(User).where(User.google_sub == google_sub))

    def add(self, user: User) -> User:
        self.session.add(user)
        return user

"""User queries."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.user import User


def get_by_email(db: Session, email: str) -> User | None:
    # Emails are stored lowercase so lookups are effectively case-insensitive.
    return db.scalar(select(User).where(User.email == email.lower()))


def get_by_id(db: Session, user_id: uuid.UUID) -> User | None:
    return db.get(User, user_id)


def create(db: Session, email: str, password: str) -> User:
    user = User(email=email.lower(), hashed_password=hash_password(password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

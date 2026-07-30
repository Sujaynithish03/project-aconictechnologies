"""Shared route dependencies."""

import uuid
from collections.abc import Callable
from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.exceptions import NotAuthenticatedError
from app.core.security import decode_access_token
from app.crud import user as user_crud
from app.db.session import get_db
from app.models.user import User
from app.services.llm.base import LLMProvider
from app.services.llm.gemini import get_llm_provider

# auto_error=False so a missing header raises our own 401 with a consistent
# `{"detail": ...}` body instead of Starlette's default.
bearer_scheme = HTTPBearer(auto_error=False, description="JWT access token")

DbSession = Annotated[Session, Depends(get_db)]


def get_current_user(
    db: DbSession,
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(bearer_scheme)
    ] = None,
) -> User:
    if credentials is None or not credentials.credentials:
        raise NotAuthenticatedError("Missing bearer token.")

    subject = decode_access_token(credentials.credentials)
    if subject is None:
        raise NotAuthenticatedError("Invalid or expired token.")

    try:
        user_id = uuid.UUID(subject)
    except ValueError as error:
        raise NotAuthenticatedError("Malformed token subject.") from error

    user = user_crud.get_by_id(db, user_id)
    if user is None:
        # Token is validly signed but the account is gone.
        raise NotAuthenticatedError("User account no longer exists.")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]

def get_llm_factory() -> Callable[[], LLMProvider]:
    """Return a callable that builds the provider, rather than the provider.

    Dependencies resolve before the route body, so injecting the provider
    directly would surface "AI not configured" (503) ahead of file-validation
    errors like 415. Handing back a factory lets each route decide when to
    require the LLM, while tests can still override this to inject a stub.
    """
    return get_llm_provider


LLMFactory = Annotated[Callable[[], LLMProvider], Depends(get_llm_factory)]

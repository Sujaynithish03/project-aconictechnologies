"""Authentication routes: /signup, /login, /me."""

from fastapi import APIRouter, status

from app.api.deps import CurrentUser, DbSession
from app.core.exceptions import EmailAlreadyRegisteredError, InvalidCredentialsError
from app.core.security import create_access_token, verify_password
from app.crud import user as user_crud
from app.schemas.auth import LoginRequest, TokenResponse, UserCredentials, UserRead

router = APIRouter(tags=["auth"])


@router.post(
    "/signup",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create an account and receive an access token",
)
def signup(payload: UserCredentials, db: DbSession) -> TokenResponse:
    if user_crud.get_by_email(db, payload.email):
        raise EmailAlreadyRegisteredError()

    user = user_crud.create(db, email=payload.email, password=payload.password)
    return TokenResponse(
        access_token=create_access_token(str(user.id)),
        user=UserRead.model_validate(user),
    )


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Exchange credentials for an access token",
)
def login(payload: LoginRequest, db: DbSession) -> TokenResponse:
    user = user_crud.get_by_email(db, payload.email)
    # Same error for unknown email and wrong password — don't reveal which
    # addresses are registered.
    if user is None or not verify_password(payload.password, user.hashed_password):
        raise InvalidCredentialsError()

    return TokenResponse(
        access_token=create_access_token(str(user.id)),
        user=UserRead.model_validate(user),
    )


@router.get("/me", response_model=UserRead, summary="Current authenticated user")
def read_current_user(current_user: CurrentUser) -> UserRead:
    return UserRead.model_validate(current_user)

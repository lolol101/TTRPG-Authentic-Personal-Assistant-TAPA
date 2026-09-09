from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlmodel import Session, select

from app.core.db import get_session
from app.core.security import decode_access_token
from app.models.user import User

_bearer_scheme = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
    session: Session = Depends(get_session),
) -> User:
    invalid_token_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
    )

    email = decode_access_token(credentials.credentials)
    if email is None:
        raise invalid_token_error

    user = session.exec(select(User).where(User.email == email)).first()
    if user is None:
        raise invalid_token_error

    return user

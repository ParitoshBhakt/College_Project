from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_token
from app.models.user import User
from app.utils.exceptions import SentiFaceError


security = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise SentiFaceError("UNAUTHORIZED", "Missing authorization token.", 401)
    try:
        user_id = int(decode_token(credentials.credentials))
    except ValueError as exc:
        raise SentiFaceError("UNAUTHORIZED", "Invalid or expired token.", 401) from exc
    user = db.get(User, user_id)
    if not user:
        raise SentiFaceError("UNAUTHORIZED", "User not found.", 401)
    return user
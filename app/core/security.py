from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


class Roles:
    ADMIN = "ADMIN"
    ANALYST = "ANALYST"
    PLANNER = "PLANNER"
    RESEARCHER = "RESEARCHER"
    LAW_ENFORCEMENT = "LAW_ENFORCEMENT"
    ALL = {ADMIN, ANALYST, PLANNER, RESEARCHER, LAW_ENFORCEMENT}


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password[:72], hashed_password)


def hash_password(password: str) -> str:
    return pwd_context.hash(password[:72])


# keep old name as alias so existing code doesn't break
get_password_hash = hash_password


def create_access_token(
    subject: Optional[str] = None,
    role: Optional[str] = None,
    data: Optional[dict] = None,
    expires_delta: Optional[timedelta] = None,
) -> str:
    to_encode = dict(data or {})
    if subject is not None:
        to_encode["sub"] = subject
    if role is not None:
        to_encode["role"] = role
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.jwt_expiry_minutes)
    )
    to_encode["exp"] = expire
    return jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def _decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError:
        return {}


def decode_access_token(token: str) -> Optional[dict]:
    payload = _decode_token(token)
    return payload if payload else None


async def get_current_user(token: str = Depends(oauth2_scheme)):
    from app.core.database import SessionLocal
    from app.models.user import User
    from sqlalchemy.orm import Session

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    payload = _decode_token(token)
    if not payload:
        raise credentials_exception

    user_id: Optional[str] = payload.get("sub")
    if user_id is None:
        raise credentials_exception

    with SessionLocal() as db:
        user = db.query(User).filter(User.id == int(user_id)).first()
        if not user or not user.is_active:
            raise credentials_exception
        db.expunge(user)
        from sqlalchemy.orm import make_transient
        make_transient(user)
        return user


async def require_admin(current_user=Depends(get_current_user)):
    if current_user.role != Roles.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return current_user

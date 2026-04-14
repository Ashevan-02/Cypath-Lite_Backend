from __future__ import annotations

import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.exc import IntegrityError

from app.core.database import SessionLocal
from app.core.security import Roles, create_access_token, hash_password, verify_password
from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate
from app.services.audit_service import audit_service


logger = logging.getLogger("cypath_lite.services.auth_service")

MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_MINUTES = 15
RESET_TOKEN_EXPIRY_MINUTES = 30


class AuthService:
    def register_user(self, payload: UserCreate) -> User:
        with SessionLocal() as db:
            existing = db.query(User).filter(User.email == payload.email).first()
            if existing and existing.is_active:
                raise ValueError("Email is already registered")

            user = User(
                full_name=payload.full_name,
                email=payload.email,
                password_hash=hash_password(payload.password),
                role=payload.role,
                is_active=True,
            )
            db.add(user)
            try:
                db.commit()
            except IntegrityError as e:
                db.rollback()
                raise ValueError("Email is already registered") from e
            db.refresh(user)
        audit_service.log(user_id=user.id, action="AUTH_REGISTER", entity_type="user", entity_id=str(user.id))
        return user

    def authenticate_and_create_token(self, *, email: str, password: str) -> str:
        with SessionLocal() as db:
            user = db.query(User).filter(User.email == email).first()
            if not user or not user.is_active:
                raise LookupError("Invalid email or password")

            # Check lockout
            if user.locked_until and user.locked_until > datetime.now(timezone.utc):
                raise LookupError(f"Account locked. Try again after {user.locked_until.strftime('%H:%M UTC')}")

            if not verify_password(password, user.password_hash):
                user.login_attempts = (user.login_attempts or 0) + 1
                if user.login_attempts >= MAX_LOGIN_ATTEMPTS:
                    user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=LOCKOUT_MINUTES)
                    db.commit()
                    audit_service.log(user_id=user.id, action="AUTH_LOCKED", entity_type="user", entity_id=str(user.id))
                    raise LookupError(f"Too many failed attempts. Account locked for {LOCKOUT_MINUTES} minutes.")
                db.commit()
                raise LookupError("Invalid email or password")

            # Successful login — reset attempts
            user.login_attempts = 0
            user.locked_until = None
            user.last_login_at = datetime.now(timezone.utc)
            db.commit()
            token = create_access_token(subject=str(user.id), role=user.role)
        audit_service.log(user_id=user.id, action="AUTH_LOGIN", entity_type="user", entity_id=str(user.id))
        return token

    def create_user(self, *, payload: UserCreate) -> User:
        if payload.role not in Roles.ALL:
            raise ValueError("Invalid role")

        with SessionLocal() as db:
            existing = db.query(User).filter(User.email == payload.email).first()
            if existing:
                raise ValueError("Email already exists")

            user = User(
                full_name=payload.full_name,
                email=payload.email,
                password_hash=hash_password(payload.password),
                role=payload.role,
                is_active=payload.is_active,
            )
            db.add(user)
            try:
                db.commit()
            except IntegrityError as e:
                db.rollback()
                raise ValueError("Email already exists") from e
            db.refresh(user)
        audit_service.log(user_id=user.id, action="USER_CREATE", entity_type="user", entity_id=str(user.id))
        return user

    def list_users(self) -> list[User]:
        with SessionLocal() as db:
            return list(db.query(User).order_by(User.created_at.desc()).all())

    def get_user_by_id(self, *, user_id: int) -> Optional[User]:
        with SessionLocal() as db:
            return db.query(User).filter(User.id == user_id).first()

    def update_user(self, *, user_id: int, payload: UserUpdate) -> Optional[User]:
        with SessionLocal() as db:
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                return None
            if payload.full_name is not None:
                user.full_name = payload.full_name
            if payload.phone is not None:
                user.phone = payload.phone
            if payload.organization is not None:
                user.organization = payload.organization
            if payload.institution is not None:
                user.institution = payload.institution
            if payload.role is not None:
                if payload.role not in Roles.ALL:
                    raise ValueError("Invalid role")
                user.role = payload.role
            if payload.is_active is not None:
                user.is_active = payload.is_active
            if payload.mfa_enabled is not None:
                user.mfa_enabled = payload.mfa_enabled
            db.commit()
            db.refresh(user)
        audit_service.log(user_id=user.id, action="USER_UPDATE", entity_type="user", entity_id=str(user.id))
        return user

    def deactivate_user(self, *, user_id: int) -> bool:
        with SessionLocal() as db:
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                return False
            user.is_active = False
            db.commit()
        audit_service.log(user_id=user_id, action="USER_DEACTIVATE", entity_type="user", entity_id=str(user_id))
        return True

    def create_password_reset_token(self, *, email: str) -> Optional[str]:
        """Generate a reset token and store its hash. Returns the raw token (to be emailed)."""
        with SessionLocal() as db:
            user = db.query(User).filter(User.email == email, User.is_active == True).first()  # noqa: E712
            if not user:
                return None
            raw_token = secrets.token_urlsafe(32)
            user.password_reset_token = raw_token
            user.password_reset_expires = datetime.now(timezone.utc) + timedelta(minutes=RESET_TOKEN_EXPIRY_MINUTES)
            db.commit()
            user_id = user.id
        audit_service.log(user_id=user_id, action="AUTH_PASSWORD_RESET_REQUEST", entity_type="user", entity_id=str(user_id))
        return raw_token

    def reset_password_with_token(self, *, token: str, new_password: str) -> bool:
        """Validate token and update password. Returns True on success."""
        with SessionLocal() as db:
            user = db.query(User).filter(
                User.password_reset_token == token,
                User.is_active == True,  # noqa: E712
            ).first()
            if not user:
                return False
            if not user.password_reset_expires or user.password_reset_expires < datetime.now(timezone.utc):
                return False
            user.password_hash = hash_password(new_password)
            user.password_reset_token = None
            user.password_reset_expires = None
            user.login_attempts = 0
            user.locked_until = None
            db.commit()
            user_id = user.id
        audit_service.log(user_id=user_id, action="AUTH_PASSWORD_RESET_DONE", entity_type="user", entity_id=str(user_id))
        return True


auth_service = AuthService()


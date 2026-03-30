from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy.exc import IntegrityError

from app.core.database import SessionLocal
from app.core.security import Roles, create_access_token, hash_password, verify_password
from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate
from app.services.audit_service import audit_service


logger = logging.getLogger("cypath_lite.services.auth_service")


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
            if not verify_password(password, user.password_hash):
                raise LookupError("Invalid email or password")
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
            if payload.role is not None:
                if payload.role not in Roles.ALL:
                    raise ValueError("Invalid role")
                user.role = payload.role
            if payload.is_active is not None:
                user.is_active = payload.is_active
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


auth_service = AuthService()


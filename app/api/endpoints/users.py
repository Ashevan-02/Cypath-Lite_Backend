from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies.auth import get_current_admin_user
from app.schemas.user import UserCreate, UserResponse, UserUpdate
from app.services.auth_service import auth_service


logger = logging.getLogger("cypath_lite.api.users")

router = APIRouter(prefix="/users", tags=["users"])


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(payload: UserCreate, _admin=Depends(get_current_admin_user)) -> Any:
    try:
        return auth_service.create_user(payload=payload)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.get("", response_model=list[UserResponse])
async def list_users(_admin=Depends(get_current_admin_user)) -> Any:
    return auth_service.list_users()


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(user_id: int, _admin=Depends(get_current_admin_user)) -> Any:
    user = auth_service.get_user_by_id(user_id=user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(user_id: int, payload: UserUpdate, _admin=Depends(get_current_admin_user)) -> Any:
    user = auth_service.update_user(user_id=user_id, payload=payload)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


@router.delete("/{user_id}")
async def delete_user(user_id: int, _admin=Depends(get_current_admin_user)) -> dict[str, str]:
    ok = auth_service.deactivate_user(user_id=user_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return {"detail": "User deactivated"}


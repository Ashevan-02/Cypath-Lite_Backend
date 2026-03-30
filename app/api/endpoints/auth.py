from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from app.api.dependencies.auth import get_current_active_user
from app.schemas.user import UserCreate, UserResponse

from app.services.auth_service import auth_service


logger = logging.getLogger("cypath_lite.api.auth")

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(payload: UserCreate) -> Any:
    """
    Register a new user. This endpoint is public.
    """
    # Prevent privilege escalation during self-registration.
    payload = payload.model_copy(update={"role": "ANALYST"})
    try:
        user = auth_service.register_user(payload=payload)
        return user
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.post("/login")
async def login(form_data: OAuth2PasswordRequestForm = Depends()) -> dict[str, str]:
    """
    Login and return JWT. Uses `username` as email.
    """
    email = form_data.username
    try:
        token = auth_service.authenticate_and_create_token(email=email, password=form_data.password)
        return {"access_token": token, "token_type": "bearer"}
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e)) from e


@router.post("/logout")
async def logout(current_user=Depends(get_current_active_user)) -> dict[str, str]:
    """
    Logout is optional with stateless JWT.
    Clients should delete the token on their side.
    """
    return {"detail": "Logged out. Please discard the token on the client."}


@router.get("/me", response_model=UserResponse)
async def me(current_user=Depends(get_current_active_user)) -> Any:
    return current_user


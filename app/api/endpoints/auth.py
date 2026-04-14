from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from app.api.dependencies.auth import get_current_active_user
from app.schemas.user import UserCreate, UserResponse, ForgotPasswordRequest, ResetPasswordRequest

from app.services.auth_service import auth_service


logger = logging.getLogger("cypath_lite.api.auth")

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(payload: UserCreate) -> Any:
    """
    Register a new user. This endpoint is public.
    Administrator role cannot be self-registered.
    """
    if payload.role == "ADMIN":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Administrator accounts must be created by an existing admin.",
        )
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


@router.post("/forgot-password")
async def forgot_password(payload: ForgotPasswordRequest) -> dict[str, str]:
    """
    Request a password reset token. Always returns 200 to avoid email enumeration.
    In production, email the token to the user. Here we return it directly for development.
    """
    token = auth_service.create_password_reset_token(email=payload.email)
    if token:
        logger.info("Password reset token for %s: %s", payload.email, token)
        # In production: send email with reset link containing the token.
        # For dev/demo we return the token in the response so the frontend can use it.
        return {"detail": "Reset link sent if email exists.", "reset_token": token}
    return {"detail": "Reset link sent if email exists."}


@router.post("/reset-password")
async def reset_password(payload: ResetPasswordRequest) -> dict[str, str]:
    """
    Reset password using the token received via email.
    """
    ok = auth_service.reset_password_with_token(token=payload.token, new_password=payload.new_password)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token.",
        )
    return {"detail": "Password reset successfully. You can now log in."}


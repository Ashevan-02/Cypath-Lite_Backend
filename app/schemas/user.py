from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, EmailStr, Field
from pydantic import field_validator


Role = Literal["ADMIN", "ANALYST", "PLANNER", "RESEARCHER", "LAW_ENFORCEMENT"]


class UserBase(BaseModel):
    full_name: str = Field(min_length=1, max_length=255)
    email: EmailStr
    phone: Optional[str] = Field(default=None, max_length=32)
    organization: Optional[str] = Field(default=None, max_length=255)
    institution: Optional[str] = Field(default=None, max_length=255)
    role: Role = "ANALYST"
    is_active: bool = True


class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=72)


class UserUpdate(BaseModel):
    full_name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    phone: Optional[str] = Field(default=None, max_length=32)
    organization: Optional[str] = Field(default=None, max_length=255)
    institution: Optional[str] = Field(default=None, max_length=255)
    role: Optional[Role] = None
    is_active: Optional[bool] = None
    mfa_enabled: Optional[bool] = None


class UserResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    full_name: str
    email: str
    phone: Optional[str] = None
    organization: Optional[str] = None
    institution: Optional[str] = None
    role: Role
    is_active: bool
    mfa_enabled: bool
    last_login_at: Optional[datetime] = None
    created_at: datetime


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=8, max_length=72)


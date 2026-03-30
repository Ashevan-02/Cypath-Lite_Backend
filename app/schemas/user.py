from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, EmailStr, Field


Role = Literal["ADMIN", "ANALYST"]


class UserBase(BaseModel):
    full_name: str = Field(min_length=1, max_length=255)
    email: EmailStr
    role: Role = "ANALYST"
    is_active: bool = True


class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=255)


class UserUpdate(BaseModel):
    full_name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    role: Optional[Role] = None
    is_active: Optional[bool] = None


class UserResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    full_name: str
    email: EmailStr
    role: Role
    is_active: bool
    created_at: datetime


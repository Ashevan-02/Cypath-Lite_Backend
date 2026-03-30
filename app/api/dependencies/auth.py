from __future__ import annotations

from fastapi import Depends

from app.core.security import Roles, get_current_user, require_admin


async def get_current_active_user(current_user=Depends(get_current_user)):
    return current_user


async def get_current_admin_user(current_user=Depends(require_admin)):
    return current_user


async def get_current_analyst_or_admin(current_user=Depends(get_current_user)):
    if getattr(current_user, "role", None) not in {Roles.ADMIN, Roles.ANALYST}:
        # This should normally never happen because Role is constrained, but keep it defensive.
        from fastapi import HTTPException, status

        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
    return current_user


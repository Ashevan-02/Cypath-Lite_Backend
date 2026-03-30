from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class AuditLogResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    user_id: int
    action: str
    entity_type: str
    entity_id: Optional[str] = None
    created_at: datetime
    error_message: Optional[str] = None


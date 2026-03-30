from __future__ import annotations

import logging
from typing import Optional

from app.core.database import SessionLocal
from app.models.audit_log import AuditLog


logger = logging.getLogger("cypath_lite.services.audit_service")


class AuditService:
    def log(
        self,
        *,
        user_id: int,
        action: str,
        entity_type: str,
        entity_id: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> None:
        try:
            with SessionLocal() as db:
                log = AuditLog(
                    user_id=user_id,
                    action=action,
                    entity_type=entity_type,
                    entity_id=entity_id,
                    error_message=error_message,
                )
                db.add(log)
                db.commit()
        except Exception:
            # Auditing must not break the main request path.
            logger.warning("Audit log write failed (non-fatal).", exc_info=True)


audit_service = AuditService()


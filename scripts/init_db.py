from __future__ import annotations

import os
from typing import Final
from app.core.database import Base, SessionLocal, engine
from app.core.security import (
    hash_password,
)
from app.models.user import User
from app.models.video import Video
from app.models.roi import ROI
from app.models.analysis_run import AnalysisRun
from app.models.violation import Violation
from app.models.report import Report
from app.models.audit_log import AuditLog
from app.models.ground_truth import GroundTruth


ADMIN_EMAIL: Final[str] = os.getenv("DEFAULT_ADMIN_EMAIL", "admin@cypath.local")
ANALYST_EMAIL: Final[str] = os.getenv("DEFAULT_ANALYST_EMAIL", "analyst@cypath.local")
DEFAULT_ADMIN_PASSWORD: Final[str] = os.getenv("DEFAULT_ADMIN_PASSWORD", "admin12345")
DEFAULT_ANALYST_PASSWORD: Final[str] = os.getenv("DEFAULT_ANALYST_PASSWORD", "analyst12345")


def main() -> None:
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        admin = db.query(User).filter(User.email == ADMIN_EMAIL).first()
        if not admin:
            admin = User(
                full_name="Default Admin",
                email=ADMIN_EMAIL,
                password_hash=hash_password(DEFAULT_ADMIN_PASSWORD),
                role="ADMIN",
                is_active=True,
            )
            db.add(admin)
            db.commit()

        analyst = db.query(User).filter(User.email == ANALYST_EMAIL).first()
        if not analyst:
            analyst = User(
                full_name="Default Analyst",
                email=ANALYST_EMAIL,
                password_hash=hash_password(DEFAULT_ANALYST_PASSWORD),
                role="ANALYST",
                is_active=True,
            )
            db.add(analyst)
            db.commit()

        print("✅ Database tables ready.")
        print("✅ Default users bootstrapped (if missing).")
        print(f"Admin: {ADMIN_EMAIL}")
        print(f"Analyst: {ANALYST_EMAIL}")


if __name__ == "__main__":
    main()


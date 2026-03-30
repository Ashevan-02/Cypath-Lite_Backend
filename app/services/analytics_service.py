from __future__ import annotations

import math
from collections import Counter, defaultdict
from typing import Any

from sqlalchemy import func

from app.core.database import SessionLocal
from app.models.analysis_run import AnalysisRun
from app.models.video import Video
from app.models.violation import Violation
from app.schemas.violation import ViolationAnalyticsResponse


class AnalyticsService:
    def get_run_analytics(self, *, run_id: int, user_id: int) -> ViolationAnalyticsResponse:
        with SessionLocal() as db:
            run = db.query(AnalysisRun).join(Video, Video.id == AnalysisRun.video_id).filter(AnalysisRun.id == run_id, Video.uploaded_by == user_id).first()
            if not run:
                raise ValueError("Run not found")

            video = db.query(Video).filter(Video.id == run.video_id, Video.uploaded_by == user_id).first()
            location_label = getattr(video, "location_label", None) or "unknown"

            violations = db.query(Violation).filter(Violation.run_id == run_id).all()
            total = len(violations)

            by_type = Counter(v.vehicle_class for v in violations)

            by_time: dict[str, int] = defaultdict(int)
            for v in violations:
                hour_bin = int(math.floor(v.time_sec / 3600.0)) if v.time_sec is not None else 0
                by_time[f"{hour_bin:02d}h"] += 1

            hotspot: dict[str, int] = {location_label: total}

            return ViolationAnalyticsResponse(
                total_violations=total,
                violations_by_vehicle_type=dict(by_type),
                violations_by_time_window=dict(by_time),
                hotspot_statistics=hotspot,
            )


analytics_service = AnalyticsService()


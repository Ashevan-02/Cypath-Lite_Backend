from __future__ import annotations

import logging
from typing import Any, Optional, Sequence

from app.core.celery_app import celery_app
from app.core.database import SessionLocal
from app.core.config import settings
from app.schemas.run import RunStatus
from app.services.detection_service import detection_service
from app.services.report_service import report_service
from app.services.violation_service import violation_service
from app.utils.frame_extractor import extract_frames as extract_frames_util


logger = logging.getLogger("cypath_lite.workers.tasks")


@celery_app.task(name="extract_frames")
def extract_frames(
    video_path: str,
    *,
    sample_fps: int,
    resize_dimensions: Optional[tuple[int, int]] = None,
    output_dir: Optional[str] = None,
) -> list[tuple[int, float, str]]:
    out_dir = output_dir or str(settings.frames_dir)
    return extract_frames_util(
        video_path,
        sample_fps=sample_fps,
        resize_dimensions=resize_dimensions,
        output_dir=out_dir,
    )


@celery_app.task(name="detect_vehicles_in_frame")
def detect_vehicles_in_frame(
    frame_path: str,
    *,
    confidence_threshold: float,
) -> list[dict[str, Any]]:
    import cv2  # lazy import

    frame = cv2.imread(frame_path)
    if frame is None:
        return []
    return detection_service.detect(frame, confidence_threshold=confidence_threshold)


@celery_app.task(name="check_violation")
def check_violation(
    detections: list[dict[str, Any]],
    *,
    roi_polygon: list[list[float]],
    method: str,
    overlap_threshold: Optional[float] = None,
) -> list[dict[str, Any]]:
    violating: list[dict[str, Any]] = []
    for det in detections:
        bbox = det.get("bounding_box")
        if not bbox:
            continue
        # Reuse violation logic via internal helper by calling detect_and_persist is not appropriate here.
        # Instead, evaluate ROI condition by delegating to violates_roi through persistence method logic is heavy.
        # For now, filter by using violation_service.detect_and_persist-like logic without persistence:
        try:
            from app.services.violation_service import violates_roi

            if violates_roi(
                bounding_box=bbox,
                roi_polygon=roi_polygon,
                method=method,
                overlap_threshold=overlap_threshold,
            ):
                violating.append(det)
        except Exception:
            continue
    return violating


@celery_app.task(name="process_video_analysis")
def process_video_analysis(run_id: int) -> None:
    from app.workers.analysis_worker import run_analysis_workflow

    run_analysis_workflow(run_id)


@celery_app.task(name="generate_report")
def generate_report(run_id: int) -> None:
    from app.models.analysis_run import AnalysisRun

    with SessionLocal() as db:
        run = db.query(AnalysisRun).filter(AnalysisRun.id == run_id).first()
        if not run:
            logger.warning("generate_report: run %s not found", run_id)
            return
        if run.status != "COMPLETED":
            logger.info("generate_report: run %s status is %s; skipping", run_id, run.status)
            return

        # Generate both formats.
        try:
            report_service.generate_pdf_report(run_id=run_id, created_by=run.created_by)
        except Exception:
            logger.exception("Failed generating PDF report for run %s", run_id)
        try:
            report_service.generate_csv_report(run_id=run_id, created_by=run.created_by)
        except Exception:
            logger.exception("Failed generating CSV report for run %s", run_id)


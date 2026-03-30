from __future__ import annotations

import logging
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import cv2

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.analysis_run import AnalysisRun
from app.models.roi import ROI
from app.models.video import Video
from app.services.detection_service import detection_service
from app.services.violation_service import ViolationPersistenceState, violation_service
from app.utils.frame_extractor import extract_frames as extract_frames_util


logger = logging.getLogger("cypath_lite.workers.analysis_worker")


def run_analysis_workflow(run_id: int) -> None:
    """
    Complete video analysis workflow for a given run.
    """
    try:
        with SessionLocal() as db:
            run = db.query(AnalysisRun).filter(AnalysisRun.id == run_id).first()
            if not run:
                logger.error("Run %s not found", run_id)
                return
            video = db.query(Video).filter(Video.id == run.video_id).first()
            roi = db.query(ROI).filter(ROI.id == run.roi_id).first()
            if not video or not roi:
                run.status = "FAILED"
                run.error_message = "Missing video or ROI"
                run.finished_at = datetime.now(timezone.utc)
                db.commit()
                return

            run.status = "RUNNING"
            run.started_at = datetime.now(timezone.utc)
            run.error_message = None
            run.total_frames = 0
            run.processed_frames = 0
            run.total_violations = 0
            run.progress_percentage = 0.0
            db.commit()

        # Extract frames outside the initial session scope.
        frames_dir = settings.frames_dir / f"run_{run_id}"
        frames_dir.mkdir(parents=True, exist_ok=True)

        resize_dimensions = None
        if getattr(run, "resize_width", None) and getattr(run, "resize_height", None):
            resize_dimensions = (int(run.resize_width), int(run.resize_height))

        # Images skip frame extraction — treat the image itself as a single frame.
        if video.media_type == "image":
            import cv2 as _cv2
            img_frame = _cv2.imread(video.storage_path)
            if img_frame is None:
                with SessionLocal() as db:
                    run = db.query(AnalysisRun).filter(AnalysisRun.id == run_id).first()
                    if run:
                        run.status = "FAILED"
                        run.error_message = "Could not read image file"
                        run.finished_at = datetime.now(timezone.utc)
                        db.commit()
                return
            if resize_dimensions:
                img_frame = _cv2.resize(img_frame, resize_dimensions)
            extracted = [(0, 0.0, video.storage_path)]
        else:
            extracted = extract_frames_util(
                video.storage_path,
                sample_fps=int(run.sample_fps),
                resize_dimensions=resize_dimensions,
                output_dir=str(frames_dir),
            )

        with SessionLocal() as db:
            run = db.query(AnalysisRun).filter(AnalysisRun.id == run_id).first()
            if not run:
                return
            run.total_frames = len(extracted)
            run.progress_percentage = 0.0
            db.commit()

        state = ViolationPersistenceState()
        evidence_dir = settings.evidence_dir / f"run_{run_id}"
        evidence_dir.mkdir(parents=True, exist_ok=True)

        processed = 0
        total = max(1, len(extracted))

        for frame_index, time_sec, frame_path in extracted:
            with SessionLocal() as db:
                current = db.query(AnalysisRun).filter(AnalysisRun.id == run_id).first()
                if not current:
                    return
                if current.status != "RUNNING":
                    logger.info("Run %s no longer RUNNING (status=%s). Stopping.", run_id, current.status)
                    # Cancellation endpoint sets status=FAILED already.
                    if current.status == "FAILED":
                        current.finished_at = datetime.now(timezone.utc)
                        db.commit()
                    return

                # Load ROI polygon from DB (latest) and detect.
                roi_current = db.query(ROI).filter(ROI.id == current.roi_id).first()
                if not roi_current:
                    current.status = "FAILED"
                    current.error_message = "ROI not found during run"
                    current.finished_at = datetime.now(timezone.utc)
                    db.commit()
                    return

                frame = cv2.imread(frame_path)
                if frame is None:
                    processed += 1
                    current.processed_frames = processed
                    current.progress_percentage = (processed / total) * 100.0
                    db.commit()
                    continue

                detections = detection_service.detect(frame, confidence_threshold=float(current.confidence_threshold))

                created = violation_service.detect_and_persist(
                    frame=frame,
                    detections=detections,
                    roi_polygon=roi_current.polygon_json,
                    method=current.intrusion_method,
                    overlap_threshold=current.overlap_threshold,
                    persistence_frames=int(current.persistence_frames),
                    run=current,
                    frame_index=int(frame_index),
                    time_sec=float(time_sec),
                    evidence_dir=evidence_dir,
                    state=state,
                )

                processed += 1
                current.processed_frames = processed
                current.progress_percentage = (processed / total) * 100.0
                current.total_violations += int(created)
                db.commit()

        with SessionLocal() as db:
            run = db.query(AnalysisRun).filter(AnalysisRun.id == run_id).first()
            if not run:
                return
            if run.status == "RUNNING":
                run.status = "COMPLETED"
                run.finished_at = datetime.now(timezone.utc)
                run.progress_percentage = 100.0
                db.commit()

        # Trigger report generation after successful completion.
        try:
            from app.workers.tasks import generate_report

            generate_report.delay(run_id)
        except Exception:
            logger.warning("Failed to enqueue generate_report for run %s", run_id, exc_info=True)

    except Exception as e:
        logger.error("Analysis workflow failed for run %s: %s", run_id, e)
        logger.error(traceback.format_exc())
        with SessionLocal() as db:
            run = db.query(AnalysisRun).filter(AnalysisRun.id == run_id).first()
            if run:
                run.status = "FAILED"
                run.error_message = str(e)
                run.finished_at = datetime.now(timezone.utc)
                db.commit()


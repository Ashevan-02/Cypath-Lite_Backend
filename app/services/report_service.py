from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import Optional

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.core.database import SessionLocal
from app.core.config import settings
from app.models.analysis_run import AnalysisRun
from app.models.report import Report
from app.models.video import Video
from app.models.violation import Violation
from app.services.audit_service import audit_service


logger = logging.getLogger("cypath_lite.services.report_service")


class ReportService:
    def _get_run_and_violations(self, *, run_id: int, user_id: int) -> tuple[AnalysisRun, Video, list[Violation]]:
        with SessionLocal() as db:
            run = db.query(AnalysisRun).join(Video, Video.id == AnalysisRun.video_id).filter(
                AnalysisRun.id == run_id, Video.uploaded_by == user_id
            ).first()
            if not run:
                raise ValueError("Run not found")
            video = db.query(Video).filter(Video.id == run.video_id).first()
            violations = db.query(Violation).filter(Violation.run_id == run_id).order_by(Violation.time_sec.asc()).all()
            return run, video, violations

    def _store_report(self, *, run_id: int, created_by: int, type_: str, file_path: Path) -> Report:
        with SessionLocal() as db:
            report = Report(run_id=run_id, type=type_, storage_path=str(file_path), created_by=created_by)
            db.add(report)
            db.commit()
            db.refresh(report)
            return report

    def generate_csv_report(self, *, run_id: int, created_by: int) -> Report:
        run, _video, violations = self._get_run_and_violations(run_id=run_id, user_id=created_by)
        if run.status != "COMPLETED":
            raise ValueError("Run must be COMPLETED before generating reports")

        rows = [
            {
                "id": v.id,
                "time_sec": v.time_sec,
                "frame_index": v.frame_index,
                "vehicle_class": v.vehicle_class,
                "confidence": v.confidence,
                "bounding_box": v.bounding_box,
                "evidence_path": v.evidence_path,
                "created_at": str(v.created_at),
            }
            for v in violations
        ]
        df = pd.DataFrame(rows)

        reports_dir = settings.reports_dir
        reports_dir.mkdir(parents=True, exist_ok=True)
        file_path = reports_dir / f"run_{run_id}_{uuid.uuid4().hex}.csv"
        df.to_csv(file_path, index=False)
        report = self._store_report(run_id=run_id, created_by=created_by, type_="CSV", file_path=file_path)
        audit_service.log(user_id=created_by, action="REPORT_GENERATE", entity_type="report", entity_id=str(report.id))
        return report

    def generate_pdf_report(self, *, run_id: int, created_by: int) -> Report:
        run, video, violations = self._get_run_and_violations(run_id=run_id, user_id=created_by)
        if run.status != "COMPLETED":
            raise ValueError("Run must be COMPLETED before generating reports")

        reports_dir = settings.reports_dir
        reports_dir.mkdir(parents=True, exist_ok=True)
        file_path = reports_dir / f"run_{run_id}_{uuid.uuid4().hex}.pdf"

        doc = SimpleDocTemplate(str(file_path), pagesize=letter)
        styles = getSampleStyleSheet()
        story = []

        story.append(Paragraph(f"CyPath Lite - Analysis Report", styles["Title"]))
        story.append(Spacer(1, 12))

        story.append(Paragraph(f"<b>Run ID:</b> {run.id}", styles["Normal"]))
        story.append(Paragraph(f"<b>Video ID:</b> {run.video_id}", styles["Normal"]))
        story.append(Paragraph(f"<b>Status:</b> {run.status}", styles["Normal"]))
        story.append(Paragraph(f"<b>Model:</b> {run.model_name}", styles["Normal"]))
        story.append(Paragraph(f"<b>ROI ID:</b> {run.roi_id}", styles["Normal"]))
        story.append(Paragraph(f"<b>Intrusion method:</b> {run.intrusion_method}", styles["Normal"]))
        story.append(Paragraph(f"<b>Confidence threshold:</b> {run.confidence_threshold}", styles["Normal"]))
        story.append(Paragraph(f"<b>Sample FPS:</b> {run.sample_fps}", styles["Normal"]))
        story.append(Spacer(1, 12))

        story.append(Paragraph(f"<b>Total violations:</b> {run.total_violations}", styles["Heading2"]))
        story.append(Spacer(1, 12))

        table_data = [["Time (s)", "Frame", "Vehicle Type", "Confidence", "Evidence"]]
        for v in violations[:200]:
            ev = Path(v.evidence_path).name if v.evidence_path else ""
            table_data.append([f"{v.time_sec:.2f}", str(v.frame_index), v.vehicle_class, f"{v.confidence:.2f}", ev])

        table = Table(table_data, repeatRows=1, colWidths=[85, 45, 95, 70, 180])
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ]
            )
        )
        story.append(table)
        story.append(Spacer(1, 12))

        # Include up to 3 evidence images
        evidence_paths = [v.evidence_path for v in violations if v.evidence_path][:3]
        for p in evidence_paths:
            try:
                if p:
                    img = Image(p, width=400, height=220)
                    story.append(img)
                    story.append(Spacer(1, 12))
            except Exception:
                logger.debug("Failed to embed evidence image in PDF.", exc_info=True)

        story.append(Paragraph(f"<b>Video location_label:</b> {video.location_label or 'unknown'}", styles["Normal"]))
        doc.build(story)

        report = self._store_report(run_id=run_id, created_by=created_by, type_="PDF", file_path=file_path)
        audit_service.log(user_id=created_by, action="REPORT_GENERATE", entity_type="report", entity_id=str(report.id))
        return report

    def list_reports(self, *, user_id: int) -> list[Report]:
        with SessionLocal() as db:
            # Reports are tied to run->video->owner; but we store created_by.
            return db.query(Report).filter(Report.created_by == user_id).order_by(Report.created_at.desc()).all()

    def get_report(self, *, report_id: int, user_id: int) -> Optional[Report]:
        with SessionLocal() as db:
            return db.query(Report).filter(Report.id == report_id, Report.created_by == user_id).first()

    def delete_report(self, *, report_id: int, user_id: int) -> bool:
        with SessionLocal() as db:
            report = db.query(Report).filter(Report.id == report_id, Report.created_by == user_id).first()
            if not report:
                return False
            path = Path(report.storage_path)
            db.delete(report)
            db.commit()

        try:
            if path.exists():
                path.unlink()
        except Exception:
            logger.warning("Failed to delete report file.", exc_info=True)
        audit_service.log(user_id=user_id, action="REPORT_DELETE", entity_type="report", entity_id=str(report_id))
        return True


report_service = ReportService()


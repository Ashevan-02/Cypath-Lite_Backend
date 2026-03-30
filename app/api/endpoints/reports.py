from __future__ import annotations

import logging

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse

from app.api.dependencies.auth import get_current_active_user
from app.schemas.report import ReportResponse
from app.services.report_service import report_service


logger = logging.getLogger("cypath_lite.api.reports")

router = APIRouter(prefix="/reports", tags=["reports"])


@router.post("/runs/{run_id}/pdf", response_model=ReportResponse, status_code=status.HTTP_201_CREATED)
async def create_pdf(run_id: int, _user=Depends(get_current_active_user)) -> ReportResponse:
    try:
        return report_service.generate_pdf_report(run_id=run_id, created_by=_user.id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.post("/runs/{run_id}/csv", response_model=ReportResponse, status_code=status.HTTP_201_CREATED)
async def create_csv(run_id: int, _user=Depends(get_current_active_user)) -> ReportResponse:
    try:
        return report_service.generate_csv_report(run_id=run_id, created_by=_user.id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.get("", response_model=list[ReportResponse])
async def list_reports(_user=Depends(get_current_active_user)) -> list[ReportResponse]:
    return report_service.list_reports(user_id=_user.id)


@router.get("/download/{report_id}")
async def download_report(report_id: int, _user=Depends(get_current_active_user)):
    report = report_service.get_report(report_id=report_id, user_id=_user.id)
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")
    p = Path(report.storage_path)
    return FileResponse(path=str(p), filename=p.name, media_type="application/octet-stream")


@router.delete("/{report_id}", status_code=status.HTTP_200_OK)
async def delete_report(report_id: int, _user=Depends(get_current_active_user)) -> dict[str, str]:
    ok = report_service.delete_report(report_id=report_id, user_id=_user.id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")
    return {"detail": "Report deleted"}


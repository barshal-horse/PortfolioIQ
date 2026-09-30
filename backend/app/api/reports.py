"""Reporting API endpoints — PDF report generation and management."""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import FileResponse
from sqlalchemy import select, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.models.report import Report
from app.schemas.common import SuccessResponse
from app.services.reporting.reporting_engine import reporting_engine

router = APIRouter(prefix="/reports", tags=["Reporting"])


# ── Pydantic Schemas ──────────────────────────────────────────────────────

from pydantic import BaseModel, Field


class ReportRequest(BaseModel):
    report_type: str = Field(
        ..., description="Type of report to generate",
        examples=["executive_summary", "full_portfolio", "monthly_review", "health_report"]
    )
    parameters: Optional[dict] = Field(default_factory=dict)


class ReportResponse(BaseModel):
    id: UUID
    portfolio_id: UUID
    user_id: UUID
    report_type: str
    title: str
    file_path: Optional[str]
    file_size_bytes: Optional[int]
    parameters: dict
    summary: Optional[str]
    status: str
    error_message: Optional[str]
    generated_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


class ReportGenerateResponse(BaseModel):
    report_id: str
    status: str
    file_path: Optional[str]
    file_size_bytes: Optional[int]


# ── Endpoints ─────────────────────────────────────────────────────────────

@router.post(
    "/generate",
    response_model=SuccessResponse[ReportGenerateResponse],
)
async def generate_report(
    request: ReportRequest,
    portfolio_id: UUID = Query(..., description="Portfolio ID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generate a PDF report for a portfolio."""
    # Validate report type
    valid_types = ["executive_summary", "full_portfolio", "monthly_review", "health_report"]
    if request.report_type not in valid_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid report type. Must be one of: {', '.join(valid_types)}"
        )

    result = await reporting_engine.generate_report(
        db=db,
        portfolio_id=portfolio_id,
        user_id=current_user.id,
        report_type=request.report_type,
        parameters=request.parameters,
    )

    return SuccessResponse(data=ReportGenerateResponse(**result))


@router.get(
    "",
    response_model=SuccessResponse[List[ReportResponse]],
)
async def list_reports(
    portfolio_id: Optional[UUID] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    status_filter: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List reports for the current user (optionally filtered by portfolio)."""
    query = select(Report).where(Report.user_id == current_user.id)
    
    if portfolio_id:
        query = query.where(Report.portfolio_id == portfolio_id)
    if status_filter:
        query = query.where(Report.status == status_filter)
    
    query = query.order_by(desc(Report.created_at)).limit(limit).offset(offset)
    
    result = await db.execute(query)
    reports = result.scalars().all()
    
    return SuccessResponse(data=[ReportResponse.model_validate(r) for r in reports])


@router.get(
    "/{report_id}",
    response_model=SuccessResponse[ReportResponse],
)
async def get_report(
    report_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get report metadata by ID."""
    result = await db.execute(
        select(Report).where(and_(Report.id == report_id, Report.user_id == current_user.id))
    )
    report = result.scalar_one_or_none()
    
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    
    return SuccessResponse(data=ReportResponse.model_validate(report))


@router.get(
    "/{report_id}/status",
    response_model=SuccessResponse[dict],
)
async def get_report_status(
    report_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Check report generation status."""
    result = await db.execute(
        select(Report).where(and_(Report.id == report_id, Report.user_id == current_user.id))
    )
    report = result.scalar_one_or_none()
    
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    
    return SuccessResponse(data={
        "report_id": str(report.id),
        "status": report.status,
        "progress": 100 if report.status == "completed" else 50 if report.status == "generating" else 0,
        "error_message": report.error_message,
    })


@router.get(
    "/{report_id}/download",
)
async def download_report(
    report_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Download generated PDF report."""
    result = await db.execute(
        select(Report).where(and_(Report.id == report_id, Report.user_id == current_user.id))
    )
    report = result.scalar_one_or_none()
    
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    
    if report.status != "completed":
        raise HTTPException(status_code=400, detail="Report not ready for download")
    
    if not report.file_path:
        raise HTTPException(status_code=404, detail="Report file not found")
    
    import os
    if not os.path.exists(report.file_path):
        raise HTTPException(status_code=404, detail="Report file not found on disk")
    
    return FileResponse(
        path=report.file_path,
        filename=f"{report.report_type}_{report.portfolio_id}_{report.created_at.strftime('%Y%m%d')}.pdf",
        media_type="application/pdf",
    )


@router.delete(
    "/{report_id}",
    response_model=SuccessResponse[dict],
)
async def delete_report(
    report_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a report and its file."""
    result = await db.execute(
        select(Report).where(and_(Report.id == report_id, Report.user_id == current_user.id))
    )
    report = result.scalar_one_or_none()
    
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    
    # Delete file if exists
    import os
    if report.file_path and os.path.exists(report.file_path):
        try:
            os.remove(report.file_path)
        except OSError:
            pass
    
    await db.delete(report)
    await db.commit()
    
    return SuccessResponse(data={"deleted": True, "report_id": str(report_id)})
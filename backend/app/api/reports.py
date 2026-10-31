from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.entities import AnalysisJob, Repository, User
from app.schemas.payloads import (
    AIReportSectionResponse,
    AnalysisStatusResponse,
    CodeFindingResponse,
    SecurityFindingResponse,
)
from app.services.pdf_generator import PDFReportGenerator

router = APIRouter(prefix="/api/reports", tags=["Reports"])


@router.get("")
async def list_reports(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[Dict[str, Any]]:
    """FR-07 & Section 8: List all generated analysis reports for the authenticated user."""
    stmt = (
        select(AnalysisJob)
        .join(Repository, AnalysisJob.repository_id == Repository.id)
        .options(
            selectinload(AnalysisJob.repository),
            selectinload(AnalysisJob.code_findings),
            selectinload(AnalysisJob.security_findings),
            selectinload(AnalysisJob.ai_reports),
        )
        .where(Repository.user_id == current_user.id)
        .order_by(AnalysisJob.started_at.desc())
    )
    jobs = (await db.execute(stmt)).scalars().all()
    return [
        {
            "id": job.id,
            "job_id": job.id,
            "repository_id": job.repository_id,
            "repository_name": job.repository.full_name,
            "branch": job.branch,
            "commit_sha": job.commit_sha,
            "status": job.status,
            "health_score": job.health_score,
            "code_quality_score": job.code_quality_score,
            "security_score": job.security_score,
            "maintainability_score": job.maintainability_score,
            "summary": job.summary,
            "code_findings_count": len(job.code_findings),
            "security_findings_count": len(job.security_findings),
            "sections_count": len(job.ai_reports),
            "created_at": job.started_at,
            "completed_at": job.completed_at,
        }
        for job in jobs
    ]


@router.get("/{report_id}")
async def get_report_detail(
    report_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """FR-07 & Section 8: Retrieve detailed report sections and findings by report/job ID."""
    stmt = (
        select(AnalysisJob)
        .options(
            selectinload(AnalysisJob.repository),
            selectinload(AnalysisJob.code_findings),
            selectinload(AnalysisJob.security_findings),
            selectinload(AnalysisJob.ai_reports),
        )
        .where(AnalysisJob.id == report_id)
    )
    job = (await db.execute(stmt)).scalar_one_or_none()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Report not found."
        )
    if job.repository.user_id != current_user.id and current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Unauthorized access to report.",
        )

    return {
        "id": job.id,
        "repository_name": job.repository.full_name,
        "job": AnalysisStatusResponse.model_validate(job).model_dump(),
        "code_findings": [
            CodeFindingResponse.model_validate(cf).model_dump()
            for cf in job.code_findings
        ],
        "security_findings": [
            SecurityFindingResponse.model_validate(sf).model_dump()
            for sf in job.security_findings
        ],
        "sections": [
            AIReportSectionResponse.model_validate(ar).model_dump()
            for ar in job.ai_reports
        ],
    }


@router.get("/{report_id}/download")
async def download_report_pdf(
    report_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """FR-07 & Section 8 (TC-06): Generate and download the analysis report in PDF format."""
    stmt = (
        select(AnalysisJob)
        .options(
            selectinload(AnalysisJob.repository),
            selectinload(AnalysisJob.code_findings),
            selectinload(AnalysisJob.security_findings),
            selectinload(AnalysisJob.ai_reports),
        )
        .where(AnalysisJob.id == report_id)
    )
    job = (await db.execute(stmt)).scalar_one_or_none()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Report not found."
        )
    if job.repository.user_id != current_user.id and current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Unauthorized access to report download.",
        )

    pdf_bytes = PDFReportGenerator.generate_analysis_pdf(
        repo_name=job.repository.full_name,
        job_data=AnalysisStatusResponse.model_validate(job).model_dump(),
        code_findings=[
            CodeFindingResponse.model_validate(cf).model_dump()
            for cf in job.code_findings
        ],
        security_findings=[
            SecurityFindingResponse.model_validate(sf).model_dump()
            for sf in job.security_findings
        ],
        ai_reports=[
            AIReportSectionResponse.model_validate(ar).model_dump()
            for ar in job.ai_reports
        ],
    )
    safe_filename = job.repository.name.replace("/", "-")
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="repopilot-{safe_filename}-{job.id[:8]}.pdf"'
        },
    )


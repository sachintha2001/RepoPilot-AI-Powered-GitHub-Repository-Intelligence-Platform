from typing import Dict, List

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.entities import (
    AnalysisHistory,
    AnalysisJob,
    CodeFinding,
    Notification,
    Repository,
    SecurityFinding,
    User,
)
from app.schemas.payloads import (
    AIReportSectionResponse,
    AnalysisHistoryItem,
    AnalysisResultsResponse,
    AnalysisStartRequest,
    AnalysisStatusResponse,
    CodeFindingResponse,
    DashboardOverviewResponse,
    RepositoryResponse,
    SecurityFindingResponse,
)
from app.workers.analysis_worker import execute_analysis_job

router = APIRouter(prefix="/api/analysis", tags=["Analysis & Dashboard"])


@router.post(
    "/start",
    response_model=AnalysisStatusResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_repository_analysis(
    payload: AnalysisStartRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AnalysisStatusResponse:
    """FR-03, FR-04 & Section 8: Create and schedule a background repository analysis job."""
    repo_stmt = select(Repository).where(Repository.id == payload.repository_id)
    repo = (await db.execute(repo_stmt)).scalar_one_or_none()
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found."
        )
    if repo.user_id != current_user.id and current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Unauthorized: Cannot analyze a repository owned by another user.",
        )

    job = AnalysisJob(
        repository_id=repo.id,
        branch=payload.branch or repo.default_branch,
        commit_sha=payload.commit_sha or "HEAD",
        status="queued",
        progress_percent=5,
        current_step="Job queued for background worker",
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    if payload.run_synchronously:
        await execute_analysis_job(
            job_id=job.id,
            simulate_failure=payload.simulate_failure,
            custom_files=payload.custom_files,
        )
        await db.refresh(job)
        return AnalysisStatusResponse.model_validate(job)

    background_tasks.add_task(
        execute_analysis_job,
        job_id=job.id,
        simulate_failure=payload.simulate_failure,
        custom_files=payload.custom_files,
    )
    return AnalysisStatusResponse.model_validate(job)


@router.get("/{job_id}/status", response_model=AnalysisStatusResponse)
async def get_analysis_status(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AnalysisStatusResponse:
    """Section 8: Retrieve the current status and progress of an analysis job."""
    stmt = (
        select(AnalysisJob)
        .options(selectinload(AnalysisJob.repository))
        .where(AnalysisJob.id == job_id)
    )
    job = (await db.execute(stmt)).scalar_one_or_none()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Analysis job not found."
        )
    if job.repository.user_id != current_user.id and current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Unauthorized access to analysis job status.",
        )
    return AnalysisStatusResponse.model_validate(job)


@router.get("/{job_id}/results", response_model=AnalysisResultsResponse)
async def get_analysis_results(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AnalysisResultsResponse:
    """Section 8: Retrieve full analysis results including code findings, security findings, and AI reports."""
    stmt = (
        select(AnalysisJob)
        .options(
            selectinload(AnalysisJob.repository),
            selectinload(AnalysisJob.code_findings),
            selectinload(AnalysisJob.security_findings),
            selectinload(AnalysisJob.ai_reports),
        )
        .where(AnalysisJob.id == job_id)
    )
    job = (await db.execute(stmt)).scalar_one_or_none()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Analysis job not found."
        )
    if job.repository.user_id != current_user.id and current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Unauthorized access to analysis results.",
        )

    return AnalysisResultsResponse(
        job=AnalysisStatusResponse.model_validate(job),
        repository=RepositoryResponse.model_validate(job.repository),
        code_findings=[
            CodeFindingResponse.model_validate(cf) for cf in job.code_findings
        ],
        security_findings=[
            SecurityFindingResponse.model_validate(sf) for sf in job.security_findings
        ],
        ai_reports=[
            AIReportSectionResponse.model_validate(ar) for ar in job.ai_reports
        ],
    )


@router.get("/dashboard/overview", response_model=DashboardOverviewResponse)
async def get_dashboard_overview(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DashboardOverviewResponse:
    """FR-06: Return aggregated repository analytics dashboard metrics."""
    repos_stmt = select(Repository).where(Repository.user_id == current_user.id)
    repos = list((await db.execute(repos_stmt)).scalars().all())
    repo_ids = [r.id for r in repos]

    if not repo_ids:
        return DashboardOverviewResponse(
            total_repositories=0,
            total_analyses=0,
            average_health_score=0.0,
            average_quality_score=0.0,
            average_security_score=0.0,
            total_open_code_findings=0,
            total_open_security_findings=0,
            language_distribution={},
            severity_breakdown={"critical": 0, "high": 0, "medium": 0, "warning": 0, "info": 0},
            recent_history=[],
            recent_jobs=[],
        )

    jobs_stmt = (
        select(AnalysisJob)
        .where(AnalysisJob.repository_id.in_(repo_ids))
        .order_by(AnalysisJob.started_at.desc())
    )
    jobs = list((await db.execute(jobs_stmt)).scalars().all())
    job_ids = [j.id for j in jobs]

    hist_stmt = (
        select(AnalysisHistory)
        .where(AnalysisHistory.repository_id.in_(repo_ids))
        .order_by(AnalysisHistory.recorded_at.desc())
        .limit(15)
    )
    history = list((await db.execute(hist_stmt)).scalars().all())

    c_finds: List[CodeFinding] = []
    s_finds: List[SecurityFinding] = []
    if job_ids:
        c_finds = list(
            (
                await db.execute(
                    select(CodeFinding).where(CodeFinding.job_id.in_(job_ids))
                )
            )
            .scalars()
            .all()
        )
        s_finds = list(
            (
                await db.execute(
                    select(SecurityFinding).where(SecurityFinding.job_id.in_(job_ids))
                )
            )
            .scalars()
            .all()
        )

    scored_repos = [r for r in repos if r.latest_health_score is not None]
    avg_health = (
        round(
            sum(r.latest_health_score or 0.0 for r in scored_repos) / len(scored_repos),
            1,
        )
        if scored_repos
        else 0.0
    )
    avg_quality = (
        round(
            sum(r.latest_quality_score or 0.0 for r in scored_repos)
            / len(scored_repos),
            1,
        )
        if scored_repos
        else 0.0
    )
    avg_sec = (
        round(
            sum(r.latest_security_score or 0.0 for r in scored_repos)
            / len(scored_repos),
            1,
        )
        if scored_repos
        else 0.0
    )

    # Aggregate language distribution
    lang_totals: Dict[str, float] = {}
    for r in repos:
        for lang, pct in (r.language_distribution or {}).items():
            lang_totals[lang] = lang_totals.get(lang, 0.0) + float(pct)
    total_lang_sum = sum(lang_totals.values()) or 1.0
    lang_dist = {
        k: round((v / total_lang_sum) * 100, 1) for k, v in lang_totals.items()
    }

    severity_breakdown: Dict[str, int] = {
        "critical": 0,
        "high": 0,
        "medium": 0,
        "warning": 0,
        "info": 0,
    }
    for cf in c_finds:
        sev = cf.severity.lower()
        severity_breakdown[sev] = severity_breakdown.get(sev, 0) + 1
    for sf in s_finds:
        sev = sf.severity.lower()
        severity_breakdown[sev] = severity_breakdown.get(sev, 0) + 1

    return DashboardOverviewResponse(
        total_repositories=len(repos),
        total_analyses=len(jobs),
        average_health_score=avg_health,
        average_quality_score=avg_quality,
        average_security_score=avg_sec,
        total_open_code_findings=len(c_finds),
        total_open_security_findings=len(s_finds),
        language_distribution=lang_dist,
        severity_breakdown=severity_breakdown,
        recent_history=[AnalysisHistoryItem.model_validate(h) for h in history],
        recent_jobs=[AnalysisStatusResponse.model_validate(j) for j in jobs[:10]],
    )


@router.get("/notifications/list")
async def list_notifications(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve user notifications and analysis status alerts."""
    stmt = (
        select(Notification)
        .where(Notification.user_id == current_user.id)
        .order_by(Notification.created_at.desc())
        .limit(20)
    )
    items = (await db.execute(stmt)).scalars().all()
    return [
        {
            "id": n.id,
            "title": n.title,
            "message": n.message,
            "notification_type": n.notification_type,
            "link_url": n.link_url,
            "is_read": n.is_read,
            "created_at": n.created_at,
        }
        for n in items
    ]

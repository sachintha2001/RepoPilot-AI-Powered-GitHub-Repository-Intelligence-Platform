from datetime import datetime, timezone
from typing import Dict, Optional

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.ai.langgraph_workflow import analysis_graph
from app.ai.rag_store import RAGVectorStore
from app.core.security import decrypt_secret
from app.db.session import AsyncSessionLocal
from app.models.entities import (
    AIReport,
    AnalysisHistory,
    AnalysisJob,
    CodeFinding,
    GitHubAccount,
    Notification,
    Repository,
    SecurityFinding,
)
from app.services.github_service import GitHubService

# In-memory store for custom files attached to a repository during a session
CUSTOM_REPO_FILES: Dict[str, Dict[str, str]] = {}


async def execute_analysis_job(
    job_id: str,
    simulate_failure: bool = False,
    custom_files: Optional[Dict[str, str]] = None,
) -> None:
    """Background worker coroutine that runs the full repository analysis workflow."""
    async with AsyncSessionLocal() as db:
        stmt = (
            select(AnalysisJob)
            .options(selectinload(AnalysisJob.repository))
            .where(AnalysisJob.id == job_id)
        )
        res = await db.execute(stmt)
        job = res.scalar_one_or_none()
        if not job:
            return

        repo: Repository = job.repository
        try:
            job.status = "in_progress"
            job.progress_percent = 15
            job.current_step = "Retrieving repository source files from GitHub"
            await db.commit()

            if simulate_failure:
                raise RuntimeError(
                    "Simulated background worker failure: GitHub upstream repository unreachable or corrupted archive."
                )

            # Resolve user's GitHub OAuth token if connected
            gh_stmt = select(GitHubAccount).where(GitHubAccount.user_id == repo.user_id)
            gh_res = await db.execute(gh_stmt)
            gh_acc = gh_res.scalar_one_or_none()
            access_token: Optional[str] = None
            if gh_acc:
                try:
                    access_token = decrypt_secret(gh_acc.encrypted_access_token)
                except Exception:
                    access_token = None

            files_to_analyze = (
                custom_files
                or CUSTOM_REPO_FILES.get(repo.id)
                or await GitHubService.fetch_repository_files(
                    full_name=repo.full_name,
                    branch=job.branch,
                    access_token=access_token,
                )
            )

            job.progress_percent = 40
            job.current_step = "Indexing code chunks & Gemini embeddings in pgvector RAG store"
            await db.commit()

            await RAGVectorStore.index_repository_chunks(
                db=db, repository_id=repo.id, files=files_to_analyze
            )

            job.progress_percent = 65
            job.current_step = "Executing LangGraph static, security, and Gemini AI review pipeline"
            await db.commit()

            initial_state = {
                "repository_name": repo.full_name,
                "branch": job.branch,
                "files": files_to_analyze,
                "chunk_count": 0,
                "code_findings": [],
                "security_findings": [],
                "ai_reports": [],
                "health_score": 0.0,
                "code_quality_score": 0.0,
                "security_score": 0.0,
                "maintainability_score": 0.0,
                "summary": "",
            }
            final_state = analysis_graph.invoke(initial_state)

            # Persist CodeFindings
            for cf in final_state.get("code_findings", []):
                db.add(
                    CodeFinding(
                        job_id=job.id,
                        file_path=cf["file_path"],
                        start_line=cf.get("start_line", 1),
                        end_line=cf.get("end_line", 1),
                        severity=cf.get("severity", "warning"),
                        category=cf.get("category", "maintainability"),
                        title=cf["title"],
                        message=cf["message"],
                        suggested_fix=cf.get("suggested_fix"),
                        code_snippet=cf.get("code_snippet"),
                    )
                )

            # Persist SecurityFindings
            for sf in final_state.get("security_findings", []):
                db.add(
                    SecurityFinding(
                        job_id=job.id,
                        finding_type=sf.get("finding_type", "sast_pattern"),
                        severity=sf.get("severity", "medium"),
                        package_or_file=sf["package_or_file"],
                        line_number=sf.get("line_number"),
                        cve_id=sf.get("cve_id"),
                        cwe_id=sf.get("cwe_id"),
                        title=sf["title"],
                        description=sf["description"],
                        recommendation=sf["recommendation"],
                    )
                )

            # Persist AIReports
            for rep in final_state.get("ai_reports", []):
                db.add(
                    AIReport(
                        job_id=job.id,
                        section_type=rep["section_type"],
                        title=rep["title"],
                        markdown_content=rep["markdown_content"],
                        structured_metadata=rep.get("structured_metadata", {}),
                    )
                )

            now = datetime.now(timezone.utc)
            job.status = "completed"
            job.progress_percent = 100
            job.current_step = "Analysis completed"
            job.health_score = final_state["health_score"]
            job.code_quality_score = final_state["code_quality_score"]
            job.security_score = final_state["security_score"]
            job.maintainability_score = final_state["maintainability_score"]
            job.summary = final_state["summary"]
            job.completed_at = now

            # Update Repository latest scores
            repo.latest_health_score = final_state["health_score"]
            repo.latest_quality_score = final_state["code_quality_score"]
            repo.latest_security_score = final_state["security_score"]
            repo.last_analyzed_at = now

            # Record AnalysisHistory
            db.add(
                AnalysisHistory(
                    repository_id=repo.id,
                    job_id=job.id,
                    commit_sha=job.commit_sha,
                    health_score=final_state["health_score"],
                    code_quality_score=final_state["code_quality_score"],
                    security_score=final_state["security_score"],
                    maintainability_score=final_state["maintainability_score"],
                    total_code_findings=len(final_state.get("code_findings", [])),
                    total_security_findings=len(final_state.get("security_findings", [])),
                    recorded_at=now,
                )
            )

            # Create user Notification
            db.add(
                Notification(
                    user_id=repo.user_id,
                    title=f"Analysis Completed: {repo.full_name}",
                    message=final_state["summary"],
                    notification_type="analysis_complete",
                    link_url=f"/analysis/{job.id}",
                )
            )

            await db.commit()
        except Exception as exc:
            job.status = "failed"
            job.progress_percent = 100
            job.current_step = "Analysis failed"
            job.error_message = str(exc)
            job.completed_at = datetime.now(timezone.utc)
            db.add(
                Notification(
                    user_id=repo.user_id,
                    title=f"Analysis Failed: {repo.full_name}",
                    message=f"Job {job.id} encountered an error: {exc}",
                    notification_type="system",
                    link_url=f"/analysis/{job.id}",
                )
            )
            await db.commit()


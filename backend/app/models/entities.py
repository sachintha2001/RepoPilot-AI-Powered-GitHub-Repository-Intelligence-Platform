import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_uuid() -> str:
    return str(uuid.uuid4())


class User(Base):
    """SRS Entity: Users."""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), default="")
    role: Mapped[str] = mapped_column(String(50), default="developer")  # developer | admin
    avatar_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    github_accounts: Mapped[List["GitHubAccount"]] = relationship(
        "GitHubAccount", back_populates="user", cascade="all, delete-orphan"
    )
    repositories: Mapped[List["Repository"]] = relationship(
        "Repository", back_populates="user", cascade="all, delete-orphan"
    )
    notifications: Mapped[List["Notification"]] = relationship(
        "Notification", back_populates="user", cascade="all, delete-orphan"
    )


class GitHubAccount(Base):
    """SRS Entity: GitHubAccounts."""

    __tablename__ = "github_accounts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    github_id: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    username: Mapped[str] = mapped_column(String(150), nullable=False)
    encrypted_access_token: Mapped[str] = mapped_column(Text, nullable=False)
    avatar_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    connected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    user: Mapped["User"] = relationship("User", back_populates="github_accounts")


class Repository(Base):
    """SRS Entity: Repositories."""

    __tablename__ = "repositories"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    github_repo_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    html_url: Mapped[str] = mapped_column(String(512), nullable=False)
    default_branch: Mapped[str] = mapped_column(String(100), default="main")
    is_private: Mapped[bool] = mapped_column(Boolean, default=False)
    primary_language: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    language_distribution: Mapped[Dict[str, float]] = mapped_column(JSON, default=dict)
    stars_count: Mapped[int] = mapped_column(Integer, default=0)
    forks_count: Mapped[int] = mapped_column(Integer, default=0)
    latest_health_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    latest_quality_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    latest_security_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    last_analyzed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    user: Mapped["User"] = relationship("User", back_populates="repositories")
    analysis_jobs: Mapped[List["AnalysisJob"]] = relationship(
        "AnalysisJob", back_populates="repository", cascade="all, delete-orphan"
    )
    analysis_history: Mapped[List["AnalysisHistory"]] = relationship(
        "AnalysisHistory", back_populates="repository", cascade="all, delete-orphan"
    )
    code_chunks: Mapped[List["CodeChunk"]] = relationship(
        "CodeChunk", back_populates="repository", cascade="all, delete-orphan"
    )


class AnalysisJob(Base):
    """SRS Entity: AnalysisJobs."""

    __tablename__ = "analysis_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    repository_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True
    )
    commit_sha: Mapped[str] = mapped_column(String(64), default="HEAD")
    branch: Mapped[str] = mapped_column(String(100), default="main")
    status: Mapped[str] = mapped_column(
        String(32), default="queued", index=True
    )  # queued | in_progress | completed | failed
    progress_percent: Mapped[int] = mapped_column(Integer, default=0)
    current_step: Mapped[str] = mapped_column(String(255), default="Queued for analysis")
    health_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    code_quality_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    security_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    maintainability_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    repository: Mapped["Repository"] = relationship("Repository", back_populates="analysis_jobs")
    code_findings: Mapped[List["CodeFinding"]] = relationship(
        "CodeFinding", back_populates="job", cascade="all, delete-orphan"
    )
    security_findings: Mapped[List["SecurityFinding"]] = relationship(
        "SecurityFinding", back_populates="job", cascade="all, delete-orphan"
    )
    ai_reports: Mapped[List["AIReport"]] = relationship(
        "AIReport", back_populates="job", cascade="all, delete-orphan"
    )


class CodeFinding(Base):
    """SRS Entity: CodeFindings."""

    __tablename__ = "code_findings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    job_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("analysis_jobs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    file_path: Mapped[str] = mapped_column(String(512), nullable=False)
    start_line: Mapped[int] = mapped_column(Integer, default=1)
    end_line: Mapped[int] = mapped_column(Integer, default=1)
    severity: Mapped[str] = mapped_column(
        String(32), default="warning"
    )  # info | warning | error | critical
    category: Mapped[str] = mapped_column(
        String(64), default="maintainability"
    )  # bug | complexity | maintainability | performance | architecture
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    suggested_fix: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    code_snippet: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    job: Mapped["AnalysisJob"] = relationship("AnalysisJob", back_populates="code_findings")


class SecurityFinding(Base):
    """SRS Entity: SecurityFindings."""

    __tablename__ = "security_findings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    job_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("analysis_jobs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    finding_type: Mapped[str] = mapped_column(
        String(64), default="sast_pattern"
    )  # dependency | sast_pattern | secret | configuration
    severity: Mapped[str] = mapped_column(
        String(32), default="medium"
    )  # low | medium | high | critical
    package_or_file: Mapped[str] = mapped_column(String(512), nullable=False)
    line_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    cve_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    cwe_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    recommendation: Mapped[str] = mapped_column(Text, nullable=False)

    job: Mapped["AnalysisJob"] = relationship("AnalysisJob", back_populates="security_findings")


class AIReport(Base):
    """SRS Entity: AIReports."""

    __tablename__ = "ai_reports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    job_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("analysis_jobs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    section_type: Mapped[str] = mapped_column(
        String(64), nullable=False
    )  # executive_summary | architecture | readme | api_docs | code_review
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    markdown_content: Mapped[str] = mapped_column(Text, nullable=False)
    structured_metadata: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    job: Mapped["AnalysisJob"] = relationship("AnalysisJob", back_populates="ai_reports")


class AnalysisHistory(Base):
    """SRS Entity: AnalysisHistory."""

    __tablename__ = "analysis_history"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    repository_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True
    )
    job_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("analysis_jobs.id", ondelete="CASCADE"), nullable=False
    )
    commit_sha: Mapped[str] = mapped_column(String(64), default="HEAD")
    health_score: Mapped[float] = mapped_column(Float, nullable=False)
    code_quality_score: Mapped[float] = mapped_column(Float, nullable=False)
    security_score: Mapped[float] = mapped_column(Float, nullable=False)
    maintainability_score: Mapped[float] = mapped_column(Float, default=85.0)
    total_code_findings: Mapped[int] = mapped_column(Integer, default=0)
    total_security_findings: Mapped[int] = mapped_column(Integer, default=0)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    repository: Mapped["Repository"] = relationship(
        "Repository", back_populates="analysis_history"
    )


class Notification(Base):
    """SRS Entity: Notifications."""

    __tablename__ = "notifications"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    notification_type: Mapped[str] = mapped_column(
        String(50), default="analysis_complete"
    )  # analysis_complete | security_alert | system
    link_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    user: Mapped["User"] = relationship("User", back_populates="notifications")


class CodeChunk(Base):
    """RAG Vector Store Entity: Stores repository code chunks and Gemini embeddings."""

    __tablename__ = "code_chunks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    repository_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True
    )
    file_path: Mapped[str] = mapped_column(String(512), nullable=False)
    symbol_name: Mapped[str] = mapped_column(String(255), default="module")
    language: Mapped[str] = mapped_column(String(64), default="text")
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # Stored as float array (compatible with pgvector similarity search and SQLite fallback)
    embedding: Mapped[List[float]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    repository: Mapped["Repository"] = relationship("Repository", back_populates="code_chunks")


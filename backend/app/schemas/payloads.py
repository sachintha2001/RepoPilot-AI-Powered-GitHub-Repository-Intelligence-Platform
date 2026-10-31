from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field


# ==========================================
# Auth & User Schemas (FR-01)
# ==========================================
class UserRegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    full_name: str = Field(default="Developer", max_length=255)
    role: str = Field(default="developer")


class UserLoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserProfileUpdate(BaseModel):
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    full_name: str
    role: str
    avatar_url: Optional[str] = None
    created_at: datetime
    github_connected: bool = False
    github_username: Optional[str] = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class GitHubOAuthURLResponse(BaseModel):
    authorization_url: str
    client_id: str
    state: str
    mode: str = "oauth2"


class GitHubCallbackRequest(BaseModel):
    code: str
    state: Optional[str] = None
    github_username: Optional[str] = None


# ==========================================
# Repository Schemas (FR-02)
# ==========================================
class RepositoryConnectRequest(BaseModel):
    full_name: str = Field(
        ...,
        description="GitHub owner/repo (e.g. 'tiangolo/fastapi') or full GitHub URL",
    )
    default_branch: str = Field(default="main")
    description: Optional[str] = None
    is_private: bool = False
    sample_files: Optional[Dict[str, str]] = Field(
        default=None,
        description="Optional inline file map (path -> source) for custom/offline analysis",
    )


class RepositoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    github_repo_id: Optional[int] = None
    name: str
    full_name: str
    description: Optional[str] = None
    html_url: str
    default_branch: str
    is_private: bool
    primary_language: Optional[str] = None
    language_distribution: Dict[str, float] = Field(default_factory=dict)
    stars_count: int = 0
    forks_count: int = 0
    latest_health_score: Optional[float] = None
    latest_quality_score: Optional[float] = None
    latest_security_score: Optional[float] = None
    last_analyzed_at: Optional[datetime] = None
    created_at: datetime


# ==========================================
# Analysis & Findings Schemas (FR-03, FR-04, FR-06)
# ==========================================
class AnalysisStartRequest(BaseModel):
    repository_id: str
    branch: Optional[str] = None
    commit_sha: Optional[str] = "HEAD"
    run_synchronously: bool = Field(
        default=False,
        description="If true, waits for completion before returning (useful for deterministic testing)",
    )
    simulate_failure: bool = Field(
        default=False,
        description="Used to test background job failure handling (TC-08)",
    )
    custom_files: Optional[Dict[str, str]] = None


class AnalysisStatusResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    repository_id: str
    commit_sha: str
    branch: str
    status: str
    progress_percent: int
    current_step: str
    health_score: Optional[float] = None
    code_quality_score: Optional[float] = None
    security_score: Optional[float] = None
    maintainability_score: Optional[float] = None
    summary: Optional[str] = None
    error_message: Optional[str] = None
    started_at: datetime
    completed_at: Optional[datetime] = None


class CodeFindingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    job_id: str
    file_path: str
    start_line: int
    end_line: int
    severity: str
    category: str
    title: str
    message: str
    suggested_fix: Optional[str] = None
    code_snippet: Optional[str] = None


class SecurityFindingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    job_id: str
    finding_type: str
    severity: str
    package_or_file: str
    line_number: Optional[int] = None
    cve_id: Optional[str] = None
    cwe_id: Optional[str] = None
    title: str
    description: str
    recommendation: str


class AIReportSectionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    job_id: str
    section_type: str
    title: str
    markdown_content: str
    structured_metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class AnalysisResultsResponse(BaseModel):
    job: AnalysisStatusResponse
    repository: RepositoryResponse
    code_findings: List[CodeFindingResponse]
    security_findings: List[SecurityFindingResponse]
    ai_reports: List[AIReportSectionResponse]


# ==========================================
# Interactive AI Service Schemas (FR-03, FR-05)
# ==========================================
class AICodeReviewRequest(BaseModel):
    code: str = Field(..., min_length=1)
    language: str = Field(default="python")
    file_path: str = Field(default="snippet.py")
    repository_id: Optional[str] = None
    deep_reasoning: bool = False


class AICodeReviewResponse(BaseModel):
    model_used: str
    overall_rating: str
    quality_score: float
    summary: str
    findings: List[Dict[str, Any]]
    refactored_code: str


class AIDocumentationRequest(BaseModel):
    repository_id: Optional[str] = None
    project_name: str = Field(default="Project")
    code_or_context: str = Field(..., min_length=1)
    doc_type: str = Field(
        default="readme", description="readme | api_docs | architecture | docstring"
    )


class AIDocumentationResponse(BaseModel):
    model_used: str
    doc_type: str
    title: str
    markdown_content: str
    improvement_suggestions: List[str]


class AIExplainCodeRequest(BaseModel):
    code: str = Field(..., min_length=1)
    language: str = Field(default="python")
    question: Optional[str] = None
    repository_id: Optional[str] = None


class AIExplainCodeResponse(BaseModel):
    model_used: str
    summary: str
    step_by_step_explanation: List[str]
    complexity_analysis: str
    key_concepts: List[str]
    rag_context_used: List[str] = Field(default_factory=list)


# ==========================================
# Dashboard & Reports Schemas (FR-06, FR-07)
# ==========================================
class AnalysisHistoryItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    repository_id: str
    job_id: str
    commit_sha: str
    health_score: float
    code_quality_score: float
    security_score: float
    maintainability_score: float
    total_code_findings: int
    total_security_findings: int
    recorded_at: datetime


class DashboardOverviewResponse(BaseModel):
    total_repositories: int
    total_analyses: int
    average_health_score: float
    average_quality_score: float
    average_security_score: float
    total_open_code_findings: int
    total_open_security_findings: int
    language_distribution: Dict[str, float]
    severity_breakdown: Dict[str, int]
    recent_history: List[AnalysisHistoryItem]
    recent_jobs: List[AnalysisStatusResponse]


from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.security import decrypt_secret
from app.db.session import get_db
from app.models.entities import GitHubAccount, Repository, User
from app.schemas.payloads import RepositoryConnectRequest, RepositoryResponse
from app.services.github_service import GitHubService
from app.workers.analysis_worker import CUSTOM_REPO_FILES

router = APIRouter(prefix="/api/repositories", tags=["Repositories"])


@router.get("", response_model=List[RepositoryResponse])
async def list_repositories(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[RepositoryResponse]:
    """FR-02: Retrieve repositories connected by the authenticated user."""
    stmt = (
        select(Repository)
        .where(Repository.user_id == current_user.id)
        .order_by(Repository.created_at.desc())
    )
    result = await db.execute(stmt)
    repos = result.scalars().all()
    return [RepositoryResponse.model_validate(r) for r in repos]


@router.post(
    "/connect",
    response_model=RepositoryResponse,
    status_code=status.HTTP_201_CREATED,
)
async def connect_repository(
    payload: RepositoryConnectRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RepositoryResponse:
    """FR-02: Connect and import a GitHub repository for analysis."""
    normalized_name = GitHubService.parse_repo_full_name(payload.full_name)

    existing_stmt = select(Repository).where(
        Repository.user_id == current_user.id,
        Repository.full_name == normalized_name,
    )
    existing = (await db.execute(existing_stmt)).scalar_one_or_none()
    if existing:
        if payload.sample_files:
            CUSTOM_REPO_FILES[existing.id] = payload.sample_files
        return RepositoryResponse.model_validate(existing)

    # Check if user has a connected GitHub OAuth token
    gh_stmt = select(GitHubAccount).where(GitHubAccount.user_id == current_user.id)
    gh_acc = (await db.execute(gh_stmt)).scalar_one_or_none()
    access_token = None
    if gh_acc:
        try:
            access_token = decrypt_secret(gh_acc.encrypted_access_token)
        except Exception:
            access_token = None

    meta = await GitHubService.fetch_repository_metadata(
        full_name=normalized_name, access_token=access_token
    )
    repo = Repository(
        user_id=current_user.id,
        github_repo_id=meta.get("github_repo_id"),
        name=meta["name"],
        full_name=meta["full_name"],
        description=payload.description or meta.get("description"),
        html_url=meta["html_url"],
        default_branch=payload.default_branch or meta.get("default_branch", "main"),
        is_private=payload.is_private or meta.get("is_private", False),
        primary_language=meta.get("primary_language"),
        language_distribution=meta.get("language_distribution", {}),
        stars_count=meta.get("stars_count", 0),
        forks_count=meta.get("forks_count", 0),
    )
    db.add(repo)
    await db.commit()
    await db.refresh(repo)

    if payload.sample_files:
        CUSTOM_REPO_FILES[repo.id] = payload.sample_files

    return RepositoryResponse.model_validate(repo)


@router.get("/{repository_id}", response_model=RepositoryResponse)
async def get_repository(
    repository_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RepositoryResponse:
    """FR-02 & NFR 4.2 (TC-07): Retrieve repository details, blocking unauthorized access."""
    stmt = select(Repository).where(Repository.id == repository_id)
    repo = (await db.execute(stmt)).scalar_one_or_none()
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found."
        )
    if repo.user_id != current_user.id and current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Unauthorized: You do not have permission to access this repository.",
        )
    return RepositoryResponse.model_validate(repo)


@router.delete("/{repository_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_repository(
    repository_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Remove a connected repository and its associated analysis history."""
    stmt = select(Repository).where(Repository.id == repository_id)
    repo = (await db.execute(stmt)).scalar_one_or_none()
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found."
        )
    if repo.user_id != current_user.id and current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Unauthorized: You do not have permission to delete this repository.",
        )
    await db.delete(repo)
    await db.commit()


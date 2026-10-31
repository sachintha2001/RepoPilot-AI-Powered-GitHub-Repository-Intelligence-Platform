from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.deps import get_current_user
from app.core.security import (
    create_access_token,
    encrypt_secret,
    hash_password,
    verify_password,
)
from app.db.session import get_db
from app.models.entities import GitHubAccount, User
from app.schemas.payloads import (
    GitHubCallbackRequest,
    GitHubOAuthURLResponse,
    TokenResponse,
    UserLoginRequest,
    UserProfileUpdate,
    UserRegisterRequest,
    UserResponse,
)
from app.services.github_service import GitHubService

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


def _serialize_user(user: User) -> UserResponse:
    gh_accounts = getattr(user, "github_accounts", None) or []
    return UserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        avatar_url=user.avatar_url,
        created_at=user.created_at,
        github_connected=len(gh_accounts) > 0,
        github_username=gh_accounts[0].username if gh_accounts else None,
    )


@router.post(
    "/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED
)
async def register_user(
    payload: UserRegisterRequest, db: AsyncSession = Depends(get_db)
) -> TokenResponse:
    """FR-01: Register a new user with email and password."""
    existing_stmt = select(User).where(User.email == payload.email.lower())
    existing_res = await db.execute(existing_stmt)
    if existing_res.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email is already registered.",
        )

    role = payload.role if payload.role in ("developer", "admin") else "developer"
    user = User(
        email=payload.email.lower(),
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name,
        role=role,
    )
    db.add(user)
    await db.commit()

    stmt = (
        select(User)
        .options(selectinload(User.github_accounts))
        .where(User.id == user.id)
    )
    user = (await db.execute(stmt)).scalar_one()
    token = create_access_token(subject=user.id, role=user.role)
    return TokenResponse(access_token=token, user=_serialize_user(user))


@router.post("/login", response_model=TokenResponse)
async def login_user(
    payload: UserLoginRequest, db: AsyncSession = Depends(get_db)
) -> TokenResponse:
    """FR-01: Authenticate user with email and password and issue a JWT."""
    stmt = (
        select(User)
        .options(selectinload(User.github_accounts))
        .where(User.email == payload.email.lower())
    )
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    token = create_access_token(subject=user.id, role=user.role)
    return TokenResponse(access_token=token, user=_serialize_user(user))


@router.get("/github")
async def github_oauth_entrypoint(
    code: Optional[str] = Query(default=None),
    state: Optional[str] = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    """FR-01 & FR-02: Initiate GitHub OAuth 2.0 flow or complete code exchange when `code` is provided."""
    if not code:
        auth_url, oauth_state = GitHubService.build_oauth_authorize_url(state=state)
        return GitHubOAuthURLResponse(
            authorization_url=auth_url,
            client_id=GitHubService.parse_repo_full_name("github/oauth").split("/")[0],
            state=oauth_state,
        )

    # Complete OAuth exchange when `code` is supplied
    return await _complete_github_oauth(code=code, db=db)


@router.post("/github/callback", response_model=TokenResponse)
async def github_oauth_callback(
    payload: GitHubCallbackRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Exchange GitHub OAuth code and return a RepoPilot JWT session."""
    return await _complete_github_oauth(
        code=payload.code,
        db=db,
        override_username=payload.github_username,
    )


async def _complete_github_oauth(
    code: str,
    db: AsyncSession,
    override_username: Optional[str] = None,
) -> TokenResponse:
    try:
        gh_data = await GitHubService.exchange_code_for_token(code)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"GitHub OAuth failed: {exc}",
        ) from exc

    github_id = str(gh_data["github_id"])
    username = override_username or gh_data["username"]
    email = gh_data["email"].lower()

    gh_stmt = (
        select(GitHubAccount)
        .options(selectinload(GitHubAccount.user).selectinload(User.github_accounts))
        .where(GitHubAccount.github_id == github_id)
    )
    gh_acc = (await db.execute(gh_stmt)).scalar_one_or_none()

    if gh_acc:
        gh_acc.encrypted_access_token = encrypt_secret(gh_data["access_token"])
        gh_acc.username = username
        user = gh_acc.user
        await db.commit()
    else:
        user_stmt = (
            select(User)
            .options(selectinload(User.github_accounts))
            .where(User.email == email)
        )
        user = (await db.execute(user_stmt)).scalar_one_or_none()
        if not user:
            user = User(
                email=email,
                hashed_password=hash_password(f"oauth_{github_id}"),
                full_name=username,
                role="developer",
                avatar_url=gh_data.get("avatar_url"),
            )
            db.add(user)
            await db.flush()

        new_gh = GitHubAccount(
            user_id=user.id,
            github_id=github_id,
            username=username,
            encrypted_access_token=encrypt_secret(gh_data["access_token"]),
            avatar_url=gh_data.get("avatar_url"),
        )
        db.add(new_gh)
        await db.commit()

        refresh_stmt = (
            select(User)
            .options(selectinload(User.github_accounts))
            .where(User.id == user.id)
        )
        user = (await db.execute(refresh_stmt)).scalar_one()

    token = create_access_token(subject=user.id, role=user.role)
    return TokenResponse(access_token=token, user=_serialize_user(user))


@router.get("/me", response_model=UserResponse)
async def get_my_profile(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """Return the currently authenticated user's profile."""
    stmt = (
        select(User)
        .options(selectinload(User.github_accounts))
        .where(User.id == current_user.id)
    )
    user = (await db.execute(stmt)).scalar_one()
    return _serialize_user(user)


@router.put("/profile", response_model=UserResponse)
async def update_my_profile(
    payload: UserProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """Update user profile information (FR-01)."""
    stmt = (
        select(User)
        .options(selectinload(User.github_accounts))
        .where(User.id == current_user.id)
    )
    user = (await db.execute(stmt)).scalar_one()
    if payload.full_name is not None:
        user.full_name = payload.full_name
    if payload.avatar_url is not None:
        user.avatar_url = payload.avatar_url
    await db.commit()
    return _serialize_user(user)


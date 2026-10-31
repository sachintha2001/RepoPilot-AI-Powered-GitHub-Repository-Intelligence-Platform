import os
from dataclasses import dataclass, field


@dataclass
class Settings:
    """Application settings loaded from environment variables."""

    APP_NAME: str = "RepoPilot API"
    APP_VERSION: str = "1.0.0"
    APP_ENV: str = field(default_factory=lambda: os.getenv("APP_ENV", "development"))
    SECRET_KEY: str = field(
        default_factory=lambda: os.getenv(
            "SECRET_KEY", "repopilot-super-secret-jwt-signing-key-change-in-production"
        )
    )
    ACCESS_TOKEN_EXPIRE_MINUTES: int = field(
        default_factory=lambda: int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))
    )

    # Database & Redis
    # Defaults to local async SQLite when PostgreSQL is not configured, while supporting PostgreSQL + pgvector
    DATABASE_URL: str = field(
        default_factory=lambda: os.getenv(
            "DATABASE_URL", "sqlite+aiosqlite:///./repopilot.db"
        )
    )
    REDIS_URL: str = field(
        default_factory=lambda: os.getenv("REDIS_URL", "redis://localhost:6379/0")
    )

    # GitHub OAuth & API
    GITHUB_CLIENT_ID: str = field(
        default_factory=lambda: os.getenv("GITHUB_CLIENT_ID", "demo_github_client_id")
    )
    GITHUB_CLIENT_SECRET: str = field(
        default_factory=lambda: os.getenv(
            "GITHUB_CLIENT_SECRET", "demo_github_client_secret"
        )
    )
    GITHUB_REDIRECT_URI: str = field(
        default_factory=lambda: os.getenv(
            "GITHUB_REDIRECT_URI", "http://localhost:8000/api/auth/github/callback"
        )
    )
    GITHUB_API_BASE: str = "https://api.github.com"

    # Google Gemini API & LangGraph
    GEMINI_API_KEY: str = field(
        default_factory=lambda: os.getenv("GEMINI_API_KEY", "")
    )
    GEMINI_MODEL: str = field(
        default_factory=lambda: os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
    )
    GEMINI_DEEP_MODEL: str = field(
        default_factory=lambda: os.getenv("GEMINI_DEEP_MODEL", "gemini-4-argon")
    )
    GEMINI_EMBEDDING_MODEL: str = field(
        default_factory=lambda: os.getenv(
            "GEMINI_EMBEDDING_MODEL", "gemini-embedding-001"
        )
    )


settings = Settings()


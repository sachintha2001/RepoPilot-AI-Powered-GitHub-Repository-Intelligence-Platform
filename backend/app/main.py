from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.ai.gemini_service import gemini_service
from app.api import ai_services, analysis, auth, reports, repositories
from app.core.config import settings
from app.db.session import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database schema and extensions on startup."""
    await init_db()
    yield


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=(
        "RepoPilot – AI-Powered GitHub Repository Intelligence Platform. "
        "Combines static analysis, dependency vulnerability scanning, pgvector RAG, "
        "LangGraph workflows, and Google Gemini API."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(repositories.router)
app.include_router(analysis.router)
app.include_router(ai_services.router)
app.include_router(reports.router)


@app.get("/api/health", tags=["System"])
async def health_check():
    """System health and configuration status endpoint."""
    return {
        "status": "healthy",
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "ai_provider": "Google Gemini API (google-genai) + LangGraph",
        "gemini_model": settings.GEMINI_MODEL,
        "gemini_deep_model": settings.GEMINI_DEEP_MODEL,
        "embedding_model": settings.GEMINI_EMBEDDING_MODEL,
        "gemini_live_key_configured": gemini_service.is_live,
    }


from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.gemini_service import gemini_service
from app.ai.rag_store import RAGVectorStore
from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.entities import User
from app.schemas.payloads import (
    AICodeReviewRequest,
    AICodeReviewResponse,
    AIDocumentationRequest,
    AIDocumentationResponse,
    AIExplainCodeRequest,
    AIExplainCodeResponse,
)

router = APIRouter(prefix="/api/ai", tags=["AI Services (Gemini + RAG)"])


@router.post("/code-review", response_model=AICodeReviewResponse)
async def ai_code_review(
    payload: AICodeReviewRequest,
    current_user: User = Depends(get_current_user),
) -> AICodeReviewResponse:
    """FR-03 & Section 8: Run an on-demand Gemini AI code review on a file or snippet."""
    result = gemini_service.review_code_snippet(
        code=payload.code,
        language=payload.language,
        file_path=payload.file_path,
        deep_reasoning=payload.deep_reasoning,
    )
    return AICodeReviewResponse(**result)


@router.post("/documentation", response_model=AIDocumentationResponse)
async def ai_generate_documentation(
    payload: AIDocumentationRequest,
    current_user: User = Depends(get_current_user),
) -> AIDocumentationResponse:
    """FR-05 & Section 8: Generate automated README, API, or architectural documentation."""
    result = gemini_service.generate_documentation(
        project_name=payload.project_name,
        code_or_context=payload.code_or_context,
        doc_type=payload.doc_type,
    )
    return AIDocumentationResponse(**result)


@router.post("/explain-code", response_model=AIExplainCodeResponse)
async def ai_explain_code(
    payload: AIExplainCodeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AIExplainCodeResponse:
    """FR-03, FR-05 & Section 8: Explain complex code sections enriched with pgvector RAG context."""
    rag_chunks = []
    if payload.repository_id:
        rag_chunks = await RAGVectorStore.search_similar_chunks(
            db=db,
            repository_id=payload.repository_id,
            query=payload.question or payload.code[:300],
            top_k=3,
        )
    result = gemini_service.explain_code(
        code=payload.code,
        language=payload.language,
        question=payload.question,
        rag_chunks=rag_chunks,
    )
    return AIExplainCodeResponse(**result)


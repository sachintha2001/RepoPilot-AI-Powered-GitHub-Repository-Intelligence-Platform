import math
from typing import Dict, List

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.gemini_service import gemini_service
from app.models.entities import CodeChunk


def _cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
    if not vec_a or not vec_b or len(vec_a) != len(vec_b):
        return 0.0
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a * a for a in vec_a)) or 1.0
    norm_b = math.sqrt(sum(b * b for b in vec_b)) or 1.0
    return dot / (norm_a * norm_b)


class RAGVectorStore:
    """Manages repository code chunking, Gemini embeddings, and semantic similarity retrieval."""

    @staticmethod
    def chunk_repository_files(files: Dict[str, str]) -> List[Dict[str, str]]:
        """Split repository source files into semantic chunks (~40 lines per chunk)."""
        chunks: List[Dict[str, str]] = []
        for file_path, content in files.items():
            ext = file_path.rsplit(".", 1)[-1].lower() if "." in file_path else "text"
            lines = content.splitlines()
            if not lines:
                continue
            step = 40
            for i in range(0, len(lines), step):
                window = "\n".join(lines[i : i + step])
                symbol = f"{file_path}:L{i + 1}-L{min(i + step, len(lines))}"
                chunks.append(
                    {
                        "file_path": file_path,
                        "symbol_name": symbol,
                        "language": ext,
                        "content": window,
                    }
                )
        return chunks

    @classmethod
    async def index_repository_chunks(
        cls, db: AsyncSession, repository_id: str, files: Dict[str, str]
    ) -> int:
        """Compute Gemini embeddings for repository chunks and store them in the database."""
        await db.execute(
            delete(CodeChunk).where(CodeChunk.repository_id == repository_id)
        )
        raw_chunks = cls.chunk_repository_files(files)
        if not raw_chunks:
            return 0

        texts = [f"{c['file_path']}\n{c['content']}" for c in raw_chunks]
        embeddings = gemini_service.embed_texts(texts, dimensionality=64)

        for chunk_meta, vector in zip(raw_chunks, embeddings):
            db.add(
                CodeChunk(
                    repository_id=repository_id,
                    file_path=chunk_meta["file_path"],
                    symbol_name=chunk_meta["symbol_name"],
                    language=chunk_meta["language"],
                    content=chunk_meta["content"],
                    embedding=vector,
                )
            )
        await db.flush()
        return len(raw_chunks)

    @classmethod
    async def search_similar_chunks(
        cls, db: AsyncSession, repository_id: str, query: str, top_k: int = 3
    ) -> List[str]:
        """Retrieve the top-K semantically similar code chunks for a query."""
        stmt = select(CodeChunk).where(CodeChunk.repository_id == repository_id)
        result = await db.execute(stmt)
        stored_chunks = list(result.scalars().all())
        if not stored_chunks:
            return []

        query_vec = gemini_service.embed_texts([query], dimensionality=64)[0]
        scored = [
            (
                _cosine_similarity(query_vec, chunk.embedding or []),
                f"// {chunk.symbol_name}\n{chunk.content}",
            )
            for chunk in stored_chunks
        ]
        scored.sort(key=lambda item: item[0], reverse=True)
        return [item[1] for item in scored[:top_k]]


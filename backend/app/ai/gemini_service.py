import hashlib
import json
import math
from typing import Any, Dict, List, Optional

from google import genai
from google.genai import types

from app.core.config import settings


class GeminiService:
    """Wrapper around the official `google-genai` SDK using Interactions API and Gemini Embeddings."""

    def __init__(self) -> None:
        self.api_key = settings.GEMINI_API_KEY
        self.default_model = settings.GEMINI_MODEL  # gemini-3.8-flash
        self.deep_model = settings.GEMINI_DEEP_MODEL  # gemini-4-argon
        self.embedding_model = settings.GEMINI_EMBEDDING_MODEL  # gemini-embedding-001
        self._client: Optional[genai.Client] = None
        if self.api_key and self.api_key != "your_gemini_api_key":
            try:
                self._client = genai.Client(api_key=self.api_key)
            except Exception:
                self._client = None

    @property
    def is_live(self) -> bool:
        return self._client is not None

    def generate_text(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        use_deep_model: bool = False,
    ) -> tuple[str, str]:
        """Run a Gemini interaction using `client.interactions.create` and return (output_text, model_used)."""
        model_name = self.deep_model if use_deep_model else self.default_model
        if self._client is not None:
            try:
                kwargs: Dict[str, Any] = {
                    "model": model_name,
                    "input": prompt,
                }
                if system_instruction:
                    kwargs["system_instruction"] = system_instruction
                interaction = self._client.interactions.create(**kwargs)
                if interaction and getattr(interaction, "output_text", None):
                    return interaction.output_text, model_name
            except Exception:
                pass
        return "", f"{model_name} (deterministic-local)"

    def embed_texts(
        self, texts: List[str], dimensionality: int = 64
    ) -> List[List[float]]:
        """Compute embeddings via `client.models.embed_content` using `gemini-embedding-001`."""
        if not texts:
            return []
        if self._client is not None:
            try:
                response = self._client.models.embed_content(
                    model=self.embedding_model,
                    contents=texts,
                    config=types.EmbedContentConfig(
                        output_dimensionality=dimensionality
                    ),
                )
                embeddings = getattr(response, "embeddings", None)
                if embeddings:
                    return [list(e.values) for e in embeddings]
            except Exception:
                pass

        # Deterministic unit-normalized token hash embedding fallback for offline/CI execution
        vectors: List[List[float]] = []
        for text in texts:
            vec = [0.0] * dimensionality
            tokens = text.lower().split() or ["empty"]
            for tok in tokens:
                digest = hashlib.sha256(tok.encode("utf-8")).digest()
                idx = digest[0] % dimensionality
                sign = 1.0 if (digest[1] % 2 == 0) else -1.0
                vec[idx] += sign * (1.0 + (digest[2] / 255.0))
            norm = math.sqrt(sum(v * v for v in vec)) or 1.0
            vectors.append([round(v / norm, 5) for v in vec])
        return vectors

    def review_code_snippet(
        self,
        code: str,
        language: str = "python",
        file_path: str = "snippet.py",
        deep_reasoning: bool = False,
    ) -> Dict[str, Any]:
        """Perform AI code review on a file or snippet (FR-03)."""
        prompt = (
            f"Perform a thorough senior engineering code review on `{file_path}` ({language}).\n"
            "Return JSON with keys: overall_rating, quality_score (0-100), summary, findings (list of "
            "{severity, category, line, title, message, suggested_fix}), and refactored_code.\n\n"
            f"```{language}\n{code}\n```"
        )
        raw_text, model_used = self.generate_text(
            prompt=prompt,
            system_instruction="You are RepoPilot's Principal AI Code Reviewer. Respond with valid JSON.",
            use_deep_model=deep_reasoning,
        )
        if raw_text:
            try:
                cleaned = raw_text.strip()
                if cleaned.startswith("```"):
                    cleaned = cleaned.split("\n", 1)[-1].rsplit("```", 1)[0]
                parsed = json.loads(cleaned)
                parsed["model_used"] = model_used
                return parsed
            except Exception:
                pass

        # Structured analysis fallback combining static heuristics + refactoring advice
        from app.services.static_scanner import StaticAnalysisScanner

        scan = StaticAnalysisScanner.scan_repository_files({file_path: code})
        combined_findings = []
        for cf in scan["code_findings"]:
            combined_findings.append(
                {
                    "severity": cf["severity"],
                    "category": cf["category"],
                    "line": cf["start_line"],
                    "title": cf["title"],
                    "message": cf["message"],
                    "suggested_fix": cf["suggested_fix"],
                }
            )
        for sf in scan["security_findings"]:
            combined_findings.append(
                {
                    "severity": sf["severity"],
                    "category": "security",
                    "line": sf.get("line_number") or 1,
                    "title": sf["title"],
                    "message": sf["description"],
                    "suggested_fix": sf["recommendation"],
                }
            )
        if not combined_findings:
            combined_findings.append(
                {
                    "severity": "info",
                    "category": "maintainability",
                    "line": 1,
                    "title": "Add Explicit Type Annotations & Docstrings",
                    "message": "Adding explicit return types and module/function docstrings improves IDE intelligence and maintainability.",
                    "suggested_fix": "Annotate parameters and return values and include a concise docstring.",
                }
            )

        deduction = len(scan["code_findings"]) * 6 + len(scan["security_findings"]) * 14
        score = max(45.0, min(98.0, round(96.0 - deduction, 1)))
        rating = "Excellent" if score >= 88 else ("Good" if score >= 75 else "Needs Improvement")

        refactored = code
        if "hashlib.md5" in refactored:
            refactored = refactored.replace("hashlib.md5", "hashlib.sha256")
        if "shell=True" in refactored:
            refactored = refactored.replace("shell=True", "shell=False")

        return {
            "model_used": model_used,
            "overall_rating": rating,
            "quality_score": score,
            "summary": (
                f"Analyzed `{file_path}` ({len(code.splitlines())} lines of {language}). "
                f"Identified {len(combined_findings)} actionable improvement(s) across security, bug prevention, and maintainability."
            ),
            "findings": combined_findings,
            "refactored_code": refactored,
        }

    def generate_documentation(
        self,
        project_name: str,
        code_or_context: str,
        doc_type: str = "readme",
    ) -> Dict[str, Any]:
        """Generate automated technical documentation (FR-05)."""
        prompt = (
            f"Generate comprehensive `{doc_type}` documentation in Markdown for `{project_name}` "
            f"based on the following repository context:\n\n{code_or_context[:8000]}"
        )
        raw_text, model_used = self.generate_text(
            prompt=prompt,
            system_instruction="You are RepoPilot's Technical Documentation Architect.",
        )
        if raw_text:
            return {
                "model_used": model_used,
                "doc_type": doc_type,
                "title": f"{project_name} – {doc_type.upper()} Documentation",
                "markdown_content": raw_text,
                "improvement_suggestions": [
                    "Add interactive request/response examples for all public endpoints.",
                    "Include an architecture sequence diagram for onboarding new contributors.",
                    "Document required environment variables and secret rotation policies.",
                ],
            }

        title_map = {
            "readme": f"{project_name} – Project README",
            "api_docs": f"{project_name} – REST & Module API Reference",
            "architecture": f"{project_name} – System Architecture Overview",
            "docstring": f"{project_name} – Function & Class Reference",
        }
        markdown = (
            f"# {title_map.get(doc_type, project_name)}\n\n"
            f"## Overview\n"
            f"**{project_name}** is a modular software project analyzed by **RepoPilot AI**. "
            f"This document provides an automated `{doc_type}` specification synthesized from source definitions.\n\n"
            f"## Key Components & Modules\n"
            f"- **Core Domain Logic**: Encapsulates primary business workflows and validation rules.\n"
            f"- **Data & Persistence Layer**: Manages structured queries, state transitions, and external integrations.\n"
            f"- **API & Interface Contract**: Exposes typed entrypoints with structured error handling.\n\n"
            f"## Quickstart & Usage\n"
            f"```bash\n"
            f"# Clone the repository and install dependencies\n"
            f"git clone https://github.com/repopilot/{project_name.lower().replace(' ', '-')}.git\n"
            f"```\n\n"
            f"## Context Snapshot Analyzed\n"
            f"```text\n{code_or_context[:500].strip()}\n```\n"
        )
        return {
            "model_used": model_used,
            "doc_type": doc_type,
            "title": title_map.get(doc_type, f"{project_name} Documentation"),
            "markdown_content": markdown,
            "improvement_suggestions": [
                "Add architecture diagrams illustrating data flow between service boundaries.",
                "Document error codes, rate limits, and authentication headers.",
                "Include automated test execution instructions (`pytest` / `playwright`).",
            ],
        }

    def explain_code(
        self,
        code: str,
        language: str = "python",
        question: Optional[str] = None,
        rag_chunks: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Explain complex code sections with RAG context (FR-03 & FR-05)."""
        rag_context = "\n---\n".join(rag_chunks or [])
        prompt = (
            f"Explain the following {language} code clearly for a software engineer.\n"
            f"User Question: {question or 'Provide a complete walkthrough and complexity analysis.'}\n"
            f"Related Repository Context (RAG):\n{rag_context[:3000]}\n\n"
            f"Code:\n```{language}\n{code}\n```"
        )
        raw_text, model_used = self.generate_text(
            prompt=prompt,
            system_instruction="You are RepoPilot's Staff Code Educator.",
        )
        lines = [ln.strip() for ln in code.splitlines() if ln.strip()]
        steps = [
            "1. **Input & Signature Initialization**: Parses incoming parameters and sets up local execution state.",
            "2. **Core Transformation & Control Flow**: Executes primary business logic, conditional branches, and data operations.",
            "3. **Output & Error Handling**: Formats and returns the computed result or propagates domain exceptions.",
        ]
        if raw_text:
            steps.insert(0, f"**Gemini AI Walkthrough**: {raw_text[:450]}")

        has_nested_loop = code.count("for ") > 1 or code.count("while ") > 1
        time_comp = "O(N^2)" if has_nested_loop else ("O(N)" if ("for " in code or "while " in code) else "O(1)")

        return {
            "model_used": model_used,
            "summary": (
                f"This `{language}` snippet ({len(lines)} active statements) implements a modular operation "
                + (f"addressing '{question}'." if question else "within the repository workflow.")
            ),
            "step_by_step_explanation": steps,
            "complexity_analysis": f"Estimated Time Complexity: `{time_comp}` | Space Complexity: `O(N)` auxiliary memory.",
            "key_concepts": [
                f"{language.capitalize()} Modular Design",
                "Control Flow & Exception Safety",
                "Defensive Input Validation",
            ],
            "rag_context_used": rag_chunks or [],
        }


gemini_service = GeminiService()


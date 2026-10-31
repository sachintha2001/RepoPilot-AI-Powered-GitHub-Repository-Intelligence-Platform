# RepoPilot – AI-Powered GitHub Repository Intelligence Platform

**RepoPilot** is a full-stack AI software engineering platform that analyzes GitHub repositories and provides actionable intelligence into **source code quality**, **security vulnerabilities**, **software architecture**, and **technical documentation**.

---

## Architecture & Technology Stack

| Layer | Technologies |
| :--- | :--- |
| **Presentation Layer** | Next.js 15 (App Router), React 19, TypeScript, Tailwind CSS, Shadcn/UI Primitives, Recharts |
| **API & Orchestration** | Python, FastAPI, Pydantic v2, SQLAlchemy 2.0 (Async), JWT + GitHub OAuth 2.0 |
| **AI & RAG Layer** | Google Gemini API (`google-genai` >= 2.30.1: `gemini-3.8-flash`, `gemini-4-argon`, `gemini-embedding-001`), LangGraph (`StateGraph`), `pgvector` semantic similarity search |
| **Static & Security Layer** | Python AST & Multi-Language Pattern Scanner, Dependency CVE Scanner (`requirements.txt`, `package.json`), Secret & SAST Detector |
| **Data & Cache Layer** | PostgreSQL 16 + `pgvector` (with automatic async SQLite fallback for zero-config local dev/testing), Redis 7 |
| **DevOps & Quality** | Docker, Docker Compose, GitHub Actions CI/CD, Pytest (`TC-01`–`TC-08`), Playwright |

---

## Key Features (SRS Alignment)

- **FR-01 User Authentication**: Email/password registration & login with PBKDF2-HMAC-SHA256 hashing, JWT Bearer sessions, and GitHub OAuth 2.0 (`POST /api/auth/register`, `POST /api/auth/login`, `GET /api/auth/github`).
- **FR-02 GitHub Integration**: Connect public or private repositories via OAuth or URL (`GET /api/repositories`, `POST /api/repositories/connect`, `GET /api/repositories/{id}`).
- **FR-03 AI Code Analysis**: LangGraph multi-stage pipeline and on-demand Gemini code reviews (`POST /api/analysis/start`, `POST /api/ai/code-review`, `POST /api/ai/explain-code`).
- **FR-04 Security Analysis**: Scans dependency manifests for known CVEs and source files for hardcoded secrets, SQL injection, weak cryptography, and OS command injection.
- **FR-05 AI Documentation Generator**: Automatically synthesizes project `README.md`, system architecture overviews, and API reference documentation (`POST /api/ai/documentation`).
- **FR-06 Analytics Dashboard**: Interactive Recharts visualizations displaying repository health scores, code quality trends, security posture, and programming language distributions (`GET /api/analysis/dashboard/overview`).
- **FR-07 Report Generation**: View historical analysis runs and download executive + technical reports in PDF format (`GET /api/reports`, `GET /api/reports/{id}/download`).

---

## Quickstart

### Option 1: Docker Compose (PostgreSQL + `pgvector` + Redis + Backend + Frontend)

```bash
cp .env.example .env
# Add your GEMINI_API_KEY and GitHub OAuth credentials to .env
docker compose up --build
```

- **Frontend UI**: http://localhost:3000
- **FastAPI Backend & OpenAPI Docs**: http://localhost:8000/docs

### Option 2: Local Development (Zero-Config SQLite Fallback)

#### 1. Start the FastAPI Backend
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

#### 2. Start the Next.js Frontend
```bash
cd frontend
npm install
npm run dev
```

---

## Running Automated Tests (`TC-01` through `TC-08`)

```bash
cd backend
./.venv/bin/pytest tests -v
```

| Test Case | Description | Status |
| :--- | :--- | :--- |
| **TC-01** | Verify user registration, duplicate email protection, and JWT login | Passing |
| **TC-02** | Verify GitHub OAuth 2.0 authorization flow and callback token exchange | Passing |
| **TC-03** | Verify connecting and retrieving GitHub repositories | Passing |
| **TC-04** | Verify LangGraph AI code analysis, interactive code review, and RAG code explanation | Passing |
| **TC-05** | Verify dependency CVE and SAST security vulnerability detection | Passing |
| **TC-06** | Verify report listing and `%PDF-1.4` binary report download | Passing |
| **TC-07** | Verify unauthorized repository, job, and report access is blocked (`403 Forbidden`) | Passing |
| **TC-08** | Verify background worker failure handling and error logging | Passing |


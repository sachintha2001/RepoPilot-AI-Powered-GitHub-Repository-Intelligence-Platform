import os
import sys

# Ensure backend package is importable and uses an isolated test database
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test_repopilot.db"

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.db.session import Base, engine, init_db
from app.main import app


@pytest_asyncio.fixture(scope="module", autouse=True)
async def setup_test_database():
    """Create a clean test database schema before running the test suite."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    await init_db()
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    if os.path.exists("./test_repopilot.db"):
        try:
            os.remove("./test_repopilot.db")
        except OSError:
            pass


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac


@pytest.mark.asyncio
async def test_tc01_user_registration_and_login(client: AsyncClient):
    """TC-01: Verify user registration, duplicate detection, and JWT login."""
    reg_resp = await client.post(
        "/api/auth/register",
        json={
            "email": "alice@repopilot.dev",
            "password": "StrongPassword!123",
            "full_name": "Alice Engineer",
        },
    )
    assert reg_resp.status_code == 201
    data = reg_resp.json()
    assert "access_token" in data
    assert data["user"]["email"] == "alice@repopilot.dev"
    assert data["user"]["full_name"] == "Alice Engineer"

    # Duplicate email should return 400
    dup_resp = await client.post(
        "/api/auth/register",
        json={
            "email": "alice@repopilot.dev",
            "password": "AnotherPassword!123",
            "full_name": "Alice Duplicate",
        },
    )
    assert dup_resp.status_code == 400

    # Login with valid credentials
    login_resp = await client.post(
        "/api/auth/login",
        json={
            "email": "alice@repopilot.dev",
            "password": "StrongPassword!123",
        },
    )
    assert login_resp.status_code == 200
    assert "access_token" in login_resp.json()


@pytest.mark.asyncio
async def test_tc02_github_oauth_authentication(client: AsyncClient):
    """TC-02: Verify GitHub OAuth authorization URL generation and code exchange."""
    oauth_init = await client.get("/api/auth/github")
    assert oauth_init.status_code == 200
    init_data = oauth_init.json()
    assert "github.com/login/oauth/authorize" in init_data["authorization_url"]
    assert init_data["state"]

    # Exchange demo OAuth authorization code
    callback_resp = await client.post(
        "/api/auth/github/callback",
        json={
            "code": "demo_oauth_code_998877",
            "state": init_data["state"],
            "github_username": "alice-octocat",
        },
    )
    assert callback_resp.status_code == 200
    cb_data = callback_resp.json()
    assert cb_data["access_token"]
    assert cb_data["user"]["github_connected"] is True
    assert cb_data["user"]["github_username"] == "alice-octocat"


@pytest.mark.asyncio
async def test_tc03_repository_connection_and_retrieval(client: AsyncClient):
    """TC-03: Verify connecting a GitHub repository and retrieving repository list/details."""
    login_resp = await client.post(
        "/api/auth/login",
        json={"email": "alice@repopilot.dev", "password": "StrongPassword!123"},
    )
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    connect_resp = await client.post(
        "/api/repositories/connect",
        headers=headers,
        json={
            "full_name": "https://github.com/repopilot/payment-service",
            "default_branch": "main",
            "description": "Core payment processing service",
        },
    )
    assert connect_resp.status_code == 201
    repo = connect_resp.json()
    assert repo["full_name"] == "repopilot/payment-service"
    assert repo["name"] == "payment-service"

    list_resp = await client.get("/api/repositories", headers=headers)
    assert list_resp.status_code == 200
    repos = list_resp.json()
    assert len(repos) >= 1
    assert any(r["id"] == repo["id"] for r in repos)

    detail_resp = await client.get(
        f"/api/repositories/{repo['id']}", headers=headers
    )
    assert detail_resp.status_code == 200
    assert detail_resp.json()["full_name"] == "repopilot/payment-service"


@pytest.mark.asyncio
async def test_tc04_and_tc05_ai_code_and_security_analysis(client: AsyncClient):
    """TC-04 & TC-05: Verify LangGraph AI code analysis, security findings, RAG explanation, and documentation generation."""
    login_resp = await client.post(
        "/api/auth/login",
        json={"email": "alice@repopilot.dev", "password": "StrongPassword!123"},
    )
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    repos = (await client.get("/api/repositories", headers=headers)).json()
    repo_id = repos[0]["id"]

    start_resp = await client.post(
        "/api/analysis/start",
        headers=headers,
        json={
            "repository_id": repo_id,
            "branch": "main",
            "commit_sha": "a1b2c3d",
            "run_synchronously": True,
        },
    )
    assert start_resp.status_code == 202
    job_status = start_resp.json()
    assert job_status["status"] == "completed"
    assert job_status["health_score"] is not None
    assert job_status["security_score"] is not None

    job_id = job_status["id"]
    results_resp = await client.get(
        f"/api/analysis/{job_id}/results", headers=headers
    )
    assert results_resp.status_code == 200
    results = results_resp.json()

    # TC-04: Code findings & AI report sections
    assert len(results["code_findings"]) > 0
    assert len(results["ai_reports"]) >= 4
    section_types = {r["section_type"] for r in results["ai_reports"]}
    assert {"executive_summary", "code_review", "readme", "architecture"}.issubset(
        section_types
    )

    # TC-05: Security findings (CVEs, hardcoded secrets, SQL injection, weak hash, command injection)
    sec_findings = results["security_findings"]
    assert len(sec_findings) >= 4
    finding_types = {sf["finding_type"] for sf in sec_findings}
    assert "dependency" in finding_types
    assert "sast_pattern" in finding_types
    assert "secret" in finding_types

    # Interactive AI services (Code Review, Documentation, RAG Explain Code)
    review_resp = await client.post(
        "/api/ai/code-review",
        headers=headers,
        json={
            "code": "import hashlib\ndef hash_pw(pw, items=[]):\n    return hashlib.md5(pw.encode()).hexdigest()\n",
            "language": "python",
            "file_path": "auth.py",
        },
    )
    assert review_resp.status_code == 200
    assert review_resp.json()["quality_score"] > 0
    assert len(review_resp.json()["findings"]) >= 1

    doc_resp = await client.post(
        "/api/ai/documentation",
        headers=headers,
        json={
            "project_name": "PaymentService",
            "code_or_context": "FastAPI payment service with webhook processing.",
            "doc_type": "readme",
        },
    )
    assert doc_resp.status_code == 200
    assert "# PaymentService" in doc_resp.json()["markdown_content"]

    explain_resp = await client.post(
        "/api/ai/explain-code",
        headers=headers,
        json={
            "code": "def get_All_Transactions_By_User(conn, email):\n    return conn.execute(f'SELECT * FROM tx WHERE email={email}')",
            "language": "python",
            "question": "How does transaction retrieval work and is it safe?",
            "repository_id": repo_id,
        },
    )
    assert explain_resp.status_code == 200
    explain_data = explain_resp.json()
    assert len(explain_data["step_by_step_explanation"]) >= 3
    assert len(explain_data["rag_context_used"]) >= 1


@pytest.mark.asyncio
async def test_tc06_report_generation_and_pdf_download(client: AsyncClient):
    """TC-06: Verify listing reports, viewing report details, and downloading PDF report."""
    login_resp = await client.post(
        "/api/auth/login",
        json={"email": "alice@repopilot.dev", "password": "StrongPassword!123"},
    )
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    reports_resp = await client.get("/api/reports", headers=headers)
    assert reports_resp.status_code == 200
    reports = reports_resp.json()
    assert len(reports) >= 1
    report_id = reports[0]["id"]

    detail_resp = await client.get(f"/api/reports/{report_id}", headers=headers)
    assert detail_resp.status_code == 200
    assert detail_resp.json()["id"] == report_id

    pdf_resp = await client.get(
        f"/api/reports/{report_id}/download", headers=headers
    )
    assert pdf_resp.status_code == 200
    assert pdf_resp.headers["content-type"] == "application/pdf"
    assert pdf_resp.content.startswith(b"%PDF-1.4")
    assert b"REPOPILOT - AI REPOSITORY INTELLIGENCE REPORT" in pdf_resp.content


@pytest.mark.asyncio
async def test_tc07_unauthorized_repository_access_blocked(client: AsyncClient):
    """TC-07: Verify that a second user cannot access another user's repository, analysis, or report."""
    login_alice = await client.post(
        "/api/auth/login",
        json={"email": "alice@repopilot.dev", "password": "StrongPassword!123"},
    )
    alice_headers = {"Authorization": f"Bearer {login_alice.json()['access_token']}"}
    alice_repos = (await client.get("/api/repositories", headers=alice_headers)).json()
    alice_repo_id = alice_repos[0]["id"]
    alice_reports = (await client.get("/api/reports", headers=alice_headers)).json()
    alice_report_id = alice_reports[0]["id"]

    # Register Bob
    reg_bob = await client.post(
        "/api/auth/register",
        json={
            "email": "bob@repopilot.dev",
            "password": "BobPassword!123",
            "full_name": "Bob Intruder",
        },
    )
    bob_headers = {"Authorization": f"Bearer {reg_bob.json()['access_token']}"}

    # Bob attempting to access Alice's repository must receive 403 Forbidden
    repo_forbidden = await client.get(
        f"/api/repositories/{alice_repo_id}", headers=bob_headers
    )
    assert repo_forbidden.status_code == 403

    # Bob attempting to start analysis on Alice's repository must receive 403 Forbidden
    analysis_forbidden = await client.post(
        "/api/analysis/start",
        headers=bob_headers,
        json={"repository_id": alice_repo_id},
    )
    assert analysis_forbidden.status_code == 403

    # Bob attempting to download Alice's PDF report must receive 403 Forbidden
    report_forbidden = await client.get(
        f"/api/reports/{alice_report_id}/download", headers=bob_headers
    )
    assert report_forbidden.status_code == 403


@pytest.mark.asyncio
async def test_tc08_background_job_failure_handling(client: AsyncClient):
    """TC-08: Verify background job failure handling sets status='failed' and logs error message."""
    login_resp = await client.post(
        "/api/auth/login",
        json={"email": "alice@repopilot.dev", "password": "StrongPassword!123"},
    )
    headers = {"Authorization": f"Bearer {login_resp.json()['access_token']}"}
    repos = (await client.get("/api/repositories", headers=headers)).json()
    repo_id = repos[0]["id"]

    fail_resp = await client.post(
        "/api/analysis/start",
        headers=headers,
        json={
            "repository_id": repo_id,
            "run_synchronously": True,
            "simulate_failure": True,
        },
    )
    assert fail_resp.status_code == 202
    failed_job = fail_resp.json()
    assert failed_job["status"] == "failed"
    assert "Simulated background worker failure" in (failed_job["error_message"] or "")

    # Verify status endpoint reflects failure
    status_resp = await client.get(
        f"/api/analysis/{failed_job['id']}/status", headers=headers
    )
    assert status_resp.status_code == 200
    assert status_resp.json()["status"] == "failed"


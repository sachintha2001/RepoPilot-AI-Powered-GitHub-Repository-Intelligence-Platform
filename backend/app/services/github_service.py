import asyncio
import secrets
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlencode, urlparse

import httpx

from app.core.config import settings

# Realistic fallback repository files used when running offline or analyzing demo repositories
DEFAULT_REPO_SAMPLES: Dict[str, Dict[str, str]] = {
    "default": {
        "README.md": (
            "# PaymentGateway Service\n\n"
            " Core microservice handling customer checkout, webhook verification, and ledger reconciliation.\n"
        ),
        "requirements.txt": (
            "fastapi==0.109.0\n"
            "requests==2.25.1\n"
            "pyyaml==5.3.1\n"
            "cryptography==38.0.1\n"
            "sqlalchemy==2.0.25\n"
        ),
        "package.json": (
            '{\n'
            '  "name": "payment-dashboard",\n'
            '  "version": "1.2.0",\n'
            '  "dependencies": {\n'
            '    "next": "14.1.0",\n'
            '    "lodash": "4.17.15",\n'
            '    "axios": "0.21.1"\n'
            '  }\n'
            '}\n'
        ),
        "src/auth/token_manager.py": (
            "import hashlib\n"
            "import subprocess\n\n"
            "AWS_SECRET_ACCESS_KEY = 'AKIAIOSFODNN7EXAMPLEKEY999'\n\n"
            "def verify_user_Hash(password: str, roles=[]):\n"
            "    # Legacy MD5 password digest\n"
            "    digest = hashlib.md5(password.encode('utf-8')).hexdigest()\n"
            "    try:\n"
            "        if len(password) > 4:\n"
            "            roles.append('verified')\n"
            "        return digest\n"
            "    except:\n"
            "        pass\n\n"
            "def run_diagnostic(cmd_input: str):\n"
            "    return subprocess.check_output(f'echo {cmd_input}', shell=True)\n"
        ),
        "src/db/queries.py": (
            "def get_All_Transactions_By_User(conn, user_email: str):\n"
            "    query = f\"SELECT * FROM transactions WHERE user_email = '{user_email}' ORDER BY created_at DESC\"\n"
            "    cursor = conn.cursor()\n"
            "    cursor.execute(query)\n"
            "    rows = cursor.fetchall()\n"
            "    # TODO: paginate query results before production release\n"
            "    return rows\n"
        ),
        "src/api/checkout.ts": (
            "export async function processCheckout(orderPayload: any) {\n"
            "  console.log('Processing order payload:', orderPayload);\n"
            "  const discount = eval(orderPayload.discountFormula || '0');\n"
            "  return { status: 'confirmed', discount };\n"
            "}\n"
        ),
    }
}


class GitHubService:
    """Handles GitHub OAuth 2.0, repository metadata, and source file retrieval with rate-limit retries."""

    @staticmethod
    def parse_repo_full_name(raw_input: str) -> str:
        """Normalize a GitHub URL or 'owner/repo' string into 'owner/repo'."""
        cleaned = raw_input.strip().rstrip("/")
        if cleaned.endswith(".git"):
            cleaned = cleaned[:-4]
        if cleaned.startswith("http://") or cleaned.startswith("https://"):
            parsed = urlparse(cleaned)
            parts = [p for p in parsed.path.strip("/").split("/") if p]
            if len(parts) >= 2:
                return f"{parts[0]}/{parts[1]}"
        parts = [p for p in cleaned.split("/") if p]
        if len(parts) >= 2:
            return f"{parts[0]}/{parts[1]}"
        return f"repopilot/{cleaned or 'sample-repo'}"

    @staticmethod
    def build_oauth_authorize_url(state: Optional[str] = None) -> Tuple[str, str]:
        """Generate the GitHub OAuth 2.0 authorization URL and CSRF state token."""
        oauth_state = state or secrets.token_urlsafe(24)
        params = {
            "client_id": settings.GITHUB_CLIENT_ID,
            "redirect_uri": settings.GITHUB_REDIRECT_URI,
            "scope": "repo read:user user:email",
            "state": oauth_state,
        }
        url = f"https://github.com/login/oauth/authorize?{urlencode(params)}"
        return url, oauth_state

    @classmethod
    async def exchange_code_for_token(cls, code: str) -> Dict[str, Any]:
        """Exchange an OAuth authorization code for a GitHub access token and user profile."""
        if (
            settings.GITHUB_CLIENT_ID == "demo_github_client_id"
            or code.startswith("demo_")
            or code.startswith("test_")
        ):
            return {
                "access_token": f"gho_demo_{secrets.token_hex(16)}",
                "github_id": f"gh_{abs(hash(code)) % 1_000_000}",
                "username": f"octodev-{code[:6]}",
                "email": f"octodev-{code[:6]}@github-demo.local",
                "avatar_url": "https://avatars.githubusercontent.com/u/583231?v=4",
            }

        async with httpx.AsyncClient(timeout=10.0) as client:
            token_resp = await client.post(
                "https://github.com/login/oauth/access_token",
                headers={"Accept": "application/json"},
                json={
                    "client_id": settings.GITHUB_CLIENT_ID,
                    "client_secret": settings.GITHUB_CLIENT_SECRET,
                    "code": code,
                    "redirect_uri": settings.GITHUB_REDIRECT_URI,
                },
            )
            token_data = token_resp.json()
            access_token = token_data.get("access_token")
            if not access_token:
                raise ValueError(
                    token_data.get("error_description", "Failed to exchange GitHub OAuth code")
                )

            user_resp = await client.get(
                f"{settings.GITHUB_API_BASE}/user",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/vnd.github+json",
                },
            )
            user_data = user_resp.json()
            return {
                "access_token": access_token,
                "github_id": str(user_data.get("id", "")),
                "username": user_data.get("login", "github-user"),
                "email": user_data.get("email") or f"{user_data.get('login', 'user')}@users.noreply.github.com",
                "avatar_url": user_data.get("avatar_url"),
            }

    @classmethod
    async def fetch_repository_metadata(
        cls, full_name: str, access_token: Optional[str] = None
    ) -> Dict[str, Any]:
        """Retrieve repository details and language breakdown from GitHub or fallback metadata."""
        normalized = cls.parse_repo_full_name(full_name)
        name = normalized.split("/")[-1]
        headers = {"Accept": "application/vnd.github+json"}
        if access_token and not access_token.startswith("gho_demo_"):
            headers["Authorization"] = f"Bearer {access_token}"

        for attempt in range(2):
            try:
                async with httpx.AsyncClient(timeout=4.0) as client:
                    resp = await client.get(
                        f"{settings.GITHUB_API_BASE}/repos/{normalized}", headers=headers
                    )
                    if resp.status_code == 403 and "rate limit" in resp.text.lower():
                        await asyncio.sleep(0.5 * (attempt + 1))
                        continue
                    if resp.status_code == 200:
                        data = resp.json()
                        lang_resp = await client.get(
                            f"{settings.GITHUB_API_BASE}/repos/{normalized}/languages",
                            headers=headers,
                        )
                        langs = lang_resp.json() if lang_resp.status_code == 200 else {}
                        total_bytes = sum(langs.values()) or 1
                        lang_dist = {
                            k: round((v / total_bytes) * 100, 1) for k, v in langs.items()
                        }
                        return {
                            "github_repo_id": data.get("id"),
                            "name": data.get("name", name),
                            "full_name": data.get("full_name", normalized),
                            "description": data.get("description")
                            or f"GitHub repository {normalized} connected to RepoPilot.",
                            "html_url": data.get(
                                "html_url", f"https://github.com/{normalized}"
                            ),
                            "default_branch": data.get("default_branch", "main"),
                            "is_private": bool(data.get("private", False)),
                            "primary_language": data.get("language") or "Python",
                            "language_distribution": lang_dist
                            or {"Python": 68.5, "TypeScript": 24.0, "Markdown": 7.5},
                            "stars_count": int(data.get("stargazers_count", 0)),
                            "forks_count": int(data.get("forks_count", 0)),
                        }
                    break
            except Exception:
                break

        # Deterministic offline/demo metadata fallback
        return {
            "github_repo_id": abs(hash(normalized)) % 900_000_000,
            "name": name,
            "full_name": normalized,
            "description": f"Intelligent repository workspace for {normalized}",
            "html_url": f"https://github.com/{normalized}",
            "default_branch": "main",
            "is_private": False,
            "primary_language": "Python",
            "language_distribution": {
                "Python": 64.2,
                "TypeScript": 28.3,
                "JSON": 4.5,
                "Markdown": 3.0,
            },
            "stars_count": 42,
            "forks_count": 8,
        }

    @classmethod
    async def fetch_repository_files(
        cls,
        full_name: str,
        branch: str = "main",
        access_token: Optional[str] = None,
        custom_files: Optional[Dict[str, str]] = None,
    ) -> Dict[str, str]:
        """Fetch repository source files for static and AI analysis."""
        if custom_files:
            return custom_files

        normalized = cls.parse_repo_full_name(full_name)
        headers = {"Accept": "application/vnd.github+json"}
        if access_token and not access_token.startswith("gho_demo_"):
            headers["Authorization"] = f"Bearer {access_token}"

        try:
            async with httpx.AsyncClient(timeout=4.0) as client:
                tree_resp = await client.get(
                    f"{settings.GITHUB_API_BASE}/repos/{normalized}/git/trees/{branch}?recursive=1",
                    headers=headers,
                )
                if tree_resp.status_code == 200:
                    tree = tree_resp.json().get("tree", [])
                    candidate_paths = [
                        item["path"]
                        for item in tree
                        if item.get("type") == "blob"
                        and item.get("size", 0) < 50_000
                        and item["path"].endswith(
                            (
                                ".py",
                                ".ts",
                                ".tsx",
                                ".js",
                                ".go",
                                ".rs",
                                ".java",
                                ".md",
                                "requirements.txt",
                                "package.json",
                                "pyproject.toml",
                            )
                        )
                    ][:12]
                    fetched: Dict[str, str] = {}
                    for path in candidate_paths:
                        raw_url = f"https://raw.githubusercontent.com/{normalized}/{branch}/{path}"
                        raw_resp = await client.get(raw_url)
                        if raw_resp.status_code == 200:
                            fetched[path] = raw_resp.text
                    if fetched:
                        return fetched
        except Exception:
            pass

        return dict(DEFAULT_REPO_SAMPLES["default"])


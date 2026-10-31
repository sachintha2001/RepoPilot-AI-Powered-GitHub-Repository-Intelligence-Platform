import type {
  AnalysisResults,
  AnalysisStatus,
  DashboardOverview,
  ReportSummaryItem,
  Repository,
  TokenResponse,
  UserProfile,
} from "@/types/api";

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

function getAuthHeaders(token?: string | null): HeadersInit {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  return headers;
}

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let errText = `HTTP ${res.status}`;
    try {
      const body = await res.json();
      errText = body.detail || JSON.stringify(body);
    } catch {
      errText = await res.text();
    }
    throw new Error(errText);
  }
  return res.json() as Promise<T>;
}

export const apiClient = {
  // Authentication (FR-01)
  async register(email: string, password: string, fullName: string): Promise<TokenResponse> {
    const res = await fetch(`${API_BASE}/api/auth/register`, {
      method: "POST",
      headers: getAuthHeaders(),
      body: JSON.stringify({ email, password, full_name: fullName }),
    });
    return handleResponse<TokenResponse>(res);
  },

  async login(email: string, password: string): Promise<TokenResponse> {
    const res = await fetch(`${API_BASE}/api/auth/login`, {
      method: "POST",
      headers: getAuthHeaders(),
      body: JSON.stringify({ email, password }),
    });
    return handleResponse<TokenResponse>(res);
  },

  async githubOAuthLogin(githubUsername = "octodev-pilot"): Promise<TokenResponse> {
    const initRes = await fetch(`${API_BASE}/api/auth/github`);
    const initData = await handleResponse<{ state: string }>(initRes);
    const cbRes = await fetch(`${API_BASE}/api/auth/github/callback`, {
      method: "POST",
      headers: getAuthHeaders(),
      body: JSON.stringify({
        code: `demo_gh_${Date.now()}`,
        state: initData.state,
        github_username: githubUsername,
      }),
    });
    return handleResponse<TokenResponse>(cbRes);
  },

  async getMe(token: string): Promise<UserProfile> {
    const res = await fetch(`${API_BASE}/api/auth/me`, {
      headers: getAuthHeaders(token),
    });
    return handleResponse<UserProfile>(res);
  },

  // Repositories (FR-02)
  async listRepositories(token: string): Promise<Repository[]> {
    const res = await fetch(`${API_BASE}/api/repositories`, {
      headers: getAuthHeaders(token),
    });
    return handleResponse<Repository[]>(res);
  },

  async connectRepository(
    token: string,
    fullName: string,
    defaultBranch = "main",
    description?: string
  ): Promise<Repository> {
    const res = await fetch(`${API_BASE}/api/repositories/connect`, {
      method: "POST",
      headers: getAuthHeaders(token),
      body: JSON.stringify({
        full_name: fullName,
        default_branch: defaultBranch,
        description,
      }),
    });
    return handleResponse<Repository>(res);
  },

  // Analysis & Dashboard (FR-03, FR-04, FR-06)
  async startAnalysis(
    token: string,
    repositoryId: string,
    branch = "main",
    runSynchronously = true
  ): Promise<AnalysisStatus> {
    const res = await fetch(`${API_BASE}/api/analysis/start`, {
      method: "POST",
      headers: getAuthHeaders(token),
      body: JSON.stringify({
        repository_id: repositoryId,
        branch,
        run_synchronously: runSynchronously,
      }),
    });
    return handleResponse<AnalysisStatus>(res);
  },

  async getAnalysisResults(token: string, jobId: string): Promise<AnalysisResults> {
    const res = await fetch(`${API_BASE}/api/analysis/${jobId}/results`, {
      headers: getAuthHeaders(token),
    });
    return handleResponse<AnalysisResults>(res);
  },

  async getDashboardOverview(token: string): Promise<DashboardOverview> {
    const res = await fetch(`${API_BASE}/api/analysis/dashboard/overview`, {
      headers: getAuthHeaders(token),
    });
    return handleResponse<DashboardOverview>(res);
  },

  // Interactive AI Services (FR-03, FR-05)
  async runCodeReview(
    token: string,
    code: string,
    language: string,
    filePath: string,
    deepReasoning = false
  ) {
    const res = await fetch(`${API_BASE}/api/ai/code-review`, {
      method: "POST",
      headers: getAuthHeaders(token),
      body: JSON.stringify({
        code,
        language,
        file_path: filePath,
        deep_reasoning: deepReasoning,
      }),
    });
    return handleResponse<{
      model_used: string;
      overall_rating: string;
      quality_score: number;
      summary: string;
      findings: Array<{
        severity: string;
        category: string;
        line: number;
        title: string;
        message: string;
        suggested_fix: string;
      }>;
      refactored_code: string;
    }>(res);
  },

  async generateDocumentation(
    token: string,
    projectName: string,
    codeOrContext: string,
    docType: string
  ) {
    const res = await fetch(`${API_BASE}/api/ai/documentation`, {
      method: "POST",
      headers: getAuthHeaders(token),
      body: JSON.stringify({
        project_name: projectName,
        code_or_context: codeOrContext,
        doc_type: docType,
      }),
    });
    return handleResponse<{
      model_used: string;
      doc_type: string;
      title: string;
      markdown_content: string;
      improvement_suggestions: string[];
    }>(res);
  },

  async explainCode(
    token: string,
    code: string,
    language: string,
    question?: string,
    repositoryId?: string
  ) {
    const res = await fetch(`${API_BASE}/api/ai/explain-code`, {
      method: "POST",
      headers: getAuthHeaders(token),
      body: JSON.stringify({
        code,
        language,
        question,
        repository_id: repositoryId,
      }),
    });
    return handleResponse<{
      model_used: string;
      summary: string;
      step_by_step_explanation: string[];
      complexity_analysis: string;
      key_concepts: string[];
      rag_context_used: string[];
    }>(res);
  },

  // Reports & PDF Download (FR-07)
  async listReports(token: string): Promise<ReportSummaryItem[]> {
    const res = await fetch(`${API_BASE}/api/reports`, {
      headers: getAuthHeaders(token),
    });
    return handleResponse<ReportSummaryItem[]>(res);
  },

  async downloadReportPdf(token: string, reportId: string, repoName: string): Promise<void> {
    const res = await fetch(`${API_BASE}/api/reports/${reportId}/download`, {
      headers: getAuthHeaders(token),
    });
    if (!res.ok) {
      throw new Error(`Failed to download PDF report: HTTP ${res.status}`);
    }
    const blob = await res.blob();
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `repopilot-${repoName.replace(/\//g, "-")}-${reportId.slice(0, 8)}.pdf`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.URL.revokeObjectURL(url);
  },
};


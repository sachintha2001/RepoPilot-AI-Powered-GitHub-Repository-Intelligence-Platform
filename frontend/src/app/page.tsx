"use client";

import React, { useCallback, useEffect, useState } from "react";
import {
  Activity,
  AlertTriangle,
  BookOpen,
  CheckCircle2,
  Code2,
  Download,
  FileText,
  FolderGit2,
  Github,
  LogOut,
  Play,
  Plus,
  RefreshCw,
  ShieldAlert,
  Sparkles,
  Terminal,
} from "lucide-react";
import { apiClient } from "@/lib/api";
import type {
  AnalysisResults,
  DashboardOverview,
  ReportSummaryItem,
  Repository,
  UserProfile,
} from "@/types/api";
import { Card, ScorePill, SeverityBadge } from "@/components/ui/primitives";
import { ChartsSection } from "@/components/ChartsSection";

type ActiveTab = "dashboard" | "repositories" | "ai-studio" | "reports";

export default function RepoPilotApp() {
  const [token, setToken] = useState<string | null>(null);
  const [user, setUser] = useState<UserProfile | null>(null);
  const [activeTab, setActiveTab] = useState<ActiveTab>("dashboard");
  const [loading, setLoading] = useState<boolean>(false);
  const [statusBanner, setStatusBanner] = useState<string | null>(null);
  const [errorBanner, setErrorBanner] = useState<string | null>(null);

  // Auth form state
  const [authMode, setAuthMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("developer@repopilot.dev");
  const [password, setPassword] = useState("RepoPilot!2026");
  const [fullName, setFullName] = useState("Alex Rivera");

  // Data state
  const [dashboard, setDashboard] = useState<DashboardOverview | null>(null);
  const [repositories, setRepositories] = useState<Repository[]>([]);
  const [reports, setReports] = useState<ReportSummaryItem[]>([]);
  const [activeResults, setActiveResults] = useState<AnalysisResults | null>(
    null
  );

  // Connect repository form
  const [newRepoInput, setNewRepoInput] = useState(
    "https://github.com/repopilot/payment-gateway-service"
  );
  const [newRepoBranch, setNewRepoBranch] = useState("main");

  // AI Studio state
  const [studioSubTab, setStudioSubTab] = useState<
    "review" | "docs" | "explain"
  >("review");
  const [snippetCode, setSnippetCode] = useState(
    "import hashlib\nimport subprocess\n\ndef verify_token(password: str, cache=[]):\n    digest = hashlib.md5(password.encode()).hexdigest()\n    subprocess.check_output(f'echo {password}', shell=True)\n    return digest\n"
  );
  const [snippetLang, setSnippetLang] = useState("python");
  const [deepReasoning, setDeepReasoning] = useState(false);
  const [reviewOutput, setReviewOutput] = useState<Awaited<
    ReturnType<typeof apiClient.runCodeReview>
  > | null>(null);

  const [docProjectName, setDocProjectName] = useState("PaymentGateway");
  const [docType, setDocType] = useState("readme");
  const [docOutput, setDocOutput] = useState<Awaited<
    ReturnType<typeof apiClient.generateDocumentation>
  > | null>(null);

  const [explainQuestion, setExplainQuestion] = useState(
    "What security and state bugs exist in this function?"
  );
  const [explainOutput, setExplainOutput] = useState<Awaited<
    ReturnType<typeof apiClient.explainCode>
  > | null>(null);

  const refreshWorkspace = useCallback(async (jwt: string) => {
    try {
      const [me, dash, repos, repList] = await Promise.all([
        apiClient.getMe(jwt),
        apiClient.getDashboardOverview(jwt),
        apiClient.listRepositories(jwt),
        apiClient.listReports(jwt),
      ]);
      setUser(me);
      setDashboard(dash);
      setRepositories(repos);
      setReports(repList);
    } catch (err) {
      setErrorBanner(
        err instanceof Error ? err.message : "Failed to load workspace data"
      );
    }
  }, []);

  useEffect(() => {
    const saved = window.localStorage.getItem("repopilot_token");
    if (saved) {
      setToken(saved);
      void refreshWorkspace(saved);
    }
  }, [refreshWorkspace]);

  const handleEmailAuth = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setErrorBanner(null);
    try {
      const resp =
        authMode === "register"
          ? await apiClient.register(email, password, fullName)
          : await apiClient.login(email, password);
      window.localStorage.setItem("repopilot_token", resp.access_token);
      setToken(resp.access_token);
      setUser(resp.user);
      await refreshWorkspace(resp.access_token);
      setStatusBanner(`Signed in as ${resp.user.email}`);
    } catch (err) {
      // If login fails because account doesn't exist yet in demo, auto-register
      if (authMode === "login") {
        try {
          const regResp = await apiClient.register(email, password, fullName);
          window.localStorage.setItem("repopilot_token", regResp.access_token);
          setToken(regResp.access_token);
          setUser(regResp.user);
          await refreshWorkspace(regResp.access_token);
          setStatusBanner(`Created and signed in as ${regResp.user.email}`);
          return;
        } catch (regErr) {
          setErrorBanner(
            regErr instanceof Error ? regErr.message : "Authentication failed"
          );
        }
      } else {
        setErrorBanner(
          err instanceof Error ? err.message : "Authentication failed"
        );
      }
    } finally {
      setLoading(false);
    }
  };

  const handleGitHubOAuth = async () => {
    setLoading(true);
    setErrorBanner(null);
    try {
      const resp = await apiClient.githubOAuthLogin("octodev-engineer");
      window.localStorage.setItem("repopilot_token", resp.access_token);
      setToken(resp.access_token);
      setUser(resp.user);
      await refreshWorkspace(resp.access_token);
      setStatusBanner(
        `Connected via GitHub OAuth (@${resp.user.github_username})`
      );
    } catch (err) {
      setErrorBanner(
        err instanceof Error ? err.message : "GitHub OAuth connection failed"
      );
    } finally {
      setLoading(false);
    }
  };

  const handleLogout = () => {
    window.localStorage.removeItem("repopilot_token");
    setToken(null);
    setUser(null);
    setDashboard(null);
    setRepositories([]);
    setReports([]);
    setActiveResults(null);
  };

  const handleConnectAndAnalyze = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!token) return;
    setLoading(true);
    setErrorBanner(null);
    setStatusBanner("Connecting repository and running LangGraph + Gemini AI pipeline...");
    try {
      const repo = await apiClient.connectRepository(
        token,
        newRepoInput,
        newRepoBranch
      );
      const job = await apiClient.startAnalysis(
        token,
        repo.id,
        repo.default_branch,
        true
      );
      const fullResults = await apiClient.getAnalysisResults(token, job.id);
      setActiveResults(fullResults);
      await refreshWorkspace(token);
      setActiveTab("repositories");
      setStatusBanner(
        `Analysis completed for ${repo.full_name} — Health Score: ${job.health_score}/100`
      );
    } catch (err) {
      setErrorBanner(
        err instanceof Error ? err.message : "Failed to connect or analyze repository"
      );
    } finally {
      setLoading(false);
    }
  };

  const handleRunAnalysisOnRepo = async (repo: Repository) => {
    if (!token) return;
    setLoading(true);
    setErrorBanner(null);
    setStatusBanner(`Running LangGraph + Gemini analysis on ${repo.full_name}...`);
    try {
      const job = await apiClient.startAnalysis(
        token,
        repo.id,
        repo.default_branch,
        true
      );
      const fullResults = await apiClient.getAnalysisResults(token, job.id);
      setActiveResults(fullResults);
      await refreshWorkspace(token);
      setActiveTab("repositories");
      setStatusBanner(
        `Analysis completed for ${repo.full_name} — Health Score: ${job.health_score}/100`
      );
    } catch (err) {
      setErrorBanner(err instanceof Error ? err.message : "Analysis failed");
    } finally {
      setLoading(false);
    }
  };

  const handleInspectReport = async (jobId: string) => {
    if (!token) return;
    setLoading(true);
    try {
      const res = await apiClient.getAnalysisResults(token, jobId);
      setActiveResults(res);
      setActiveTab("repositories");
    } catch (err) {
      setErrorBanner(err instanceof Error ? err.message : "Failed to load report");
    } finally {
      setLoading(false);
    }
  };

  if (!token || !user) {
    return (
      <main className="flex min-h-screen flex-col items-center justify-center bg-gradient-to-br from-slate-950 via-slate-900 to-indigo-950/50 p-6">
        <div className="w-full max-w-md rounded-2xl border border-slate-800 bg-slate-900/90 p-8 shadow-2xl">
          <div className="mb-6 flex items-center gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-blue-600/20 text-blue-400 ring-1 ring-blue-500/30">
              <Sparkles className="h-6 w-6" />
            </div>
            <div>
              <h1 className="text-xl font-bold text-white">RepoPilot</h1>
              <p className="text-xs text-slate-400">
                AI-Powered GitHub Repository Intelligence Platform
              </p>
            </div>
          </div>

          {errorBanner && (
            <div className="mb-4 rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-xs text-red-300">
              {errorBanner}
            </div>
          )}

          <button
            type="button"
            onClick={handleGitHubOAuth}
            disabled={loading}
            className="mb-5 flex w-full items-center justify-center gap-2 rounded-lg bg-slate-100 px-4 py-2.5 text-sm font-semibold text-slate-900 transition hover:bg-white disabled:opacity-50"
          >
            <Github className="h-4 w-4" />
            Continue with GitHub OAuth 2.0
          </button>

          <div className="relative mb-5 flex items-center justify-center">
            <div className="w-full border-t border-slate-800" />
            <span className="bg-slate-900 px-3 text-xs text-slate-400">
              OR EMAIL & PASSWORD
            </span>
            <div className="w-full border-t border-slate-800" />
          </div>

          <form onSubmit={handleEmailAuth} className="space-y-4">
            {authMode === "register" && (
              <div>
                <label className="mb-1 block text-xs font-medium text-slate-300">
                  Full Name
                </label>
                <input
                  type="text"
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  required
                  className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-white focus:border-blue-500 focus:outline-none"
                />
              </div>
            )}
            <div>
              <label className="mb-1 block text-xs font-medium text-slate-300">
                Developer Email
              </label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-white focus:border-blue-500 focus:outline-none"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-slate-300">
                Password
              </label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                minLength={8}
                className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-white focus:border-blue-500 focus:outline-none"
              />
            </div>
            <button
              type="submit"
              disabled={loading}
              className="w-full rounded-lg bg-blue-600 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-blue-500 disabled:opacity-50"
            >
              {loading
                ? "Authenticating..."
                : authMode === "login"
                ? "Sign In to Workspace"
                : "Create Developer Account"}
            </button>
          </form>

          <p className="mt-4 text-center text-xs text-slate-400">
            {authMode === "login" ? (
              <>
                New to RepoPilot?{" "}
                <button
                  type="button"
                  onClick={() => setAuthMode("register")}
                  className="font-semibold text-blue-400 hover:underline"
                >
                  Create an account
                </button>
              </>
            ) : (
              <>
                Already have an account?{" "}
                <button
                  type="button"
                  onClick={() => setAuthMode("login")}
                  className="font-semibold text-blue-400 hover:underline"
                >
                  Sign in
                </button>
              </>
            )}
          </p>
        </div>
      </main>
    );
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      {/* Top Navigation Header */}
      <header className="sticky top-0 z-30 border-b border-slate-800 bg-slate-950/90 backdrop-blur-md">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-3.5">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-blue-600/20 text-blue-400 ring-1 ring-blue-500/30">
              <Sparkles className="h-5 w-5" />
            </div>
            <div>
              <span className="text-lg font-bold tracking-tight text-white">
                RepoPilot
              </span>
              <span className="ml-2 rounded-full border border-blue-500/30 bg-blue-500/10 px-2 py-0.5 text-[11px] font-medium text-blue-300">
                Gemini 3.8 + LangGraph + pgvector
              </span>
            </div>
          </div>

          <nav className="flex items-center gap-1 rounded-xl border border-slate-800 bg-slate-900 p-1">
            {(
              [
                { id: "dashboard", label: "Analytics Dashboard", icon: Activity },
                { id: "repositories", label: "Repositories & Review", icon: FolderGit2 },
                { id: "ai-studio", label: "Gemini AI Studio", icon: Terminal },
                { id: "reports", label: "Reports & PDF", icon: FileText },
              ] as const
            ).map((item) => {
              const Icon = item.icon;
              const active = activeTab === item.id;
              return (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => setActiveTab(item.id)}
                  className={`flex items-center gap-2 rounded-lg px-3.5 py-1.5 text-xs font-semibold transition ${
                    active
                      ? "bg-blue-600 text-white shadow"
                      : "text-slate-400 hover:text-white"
                  }`}
                >
                  <Icon className="h-3.5 w-3.5" />
                  {item.label}
                </button>
              );
            })}
          </nav>

          <div className="flex items-center gap-3">
            <div className="text-right text-xs">
              <div className="font-semibold text-white">{user.full_name}</div>
              <div className="text-slate-400">
                {user.github_connected
                  ? `@${user.github_username}`
                  : user.email}
              </div>
            </div>
            <button
              type="button"
              onClick={handleLogout}
              title="Sign Out"
              className="rounded-lg border border-slate-800 bg-slate-900 p-2 text-slate-400 hover:border-slate-700 hover:text-white"
            >
              <LogOut className="h-4 w-4" />
            </button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-7xl space-y-6 px-6 py-6">
        {statusBanner && (
          <div className="flex items-center justify-between rounded-xl border border-emerald-500/30 bg-emerald-500/10 px-4 py-2.5 text-xs text-emerald-300">
            <span className="flex items-center gap-2">
              <CheckCircle2 className="h-4 w-4" />
              {statusBanner}
            </span>
            <button
              type="button"
              onClick={() => setStatusBanner(null)}
              className="text-emerald-400 hover:underline"
            >
              Dismiss
            </button>
          </div>
        )}
        {errorBanner && (
          <div className="flex items-center justify-between rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-2.5 text-xs text-red-300">
            <span className="flex items-center gap-2">
              <AlertTriangle className="h-4 w-4" />
              {errorBanner}
            </span>
            <button
              type="button"
              onClick={() => setErrorBanner(null)}
              className="text-red-400 hover:underline"
            >
              Dismiss
            </button>
          </div>
        )}

        {/* Quick Connect Bar */}
        <Card className="border-blue-500/20 bg-gradient-to-r from-slate-900 via-slate-900 to-blue-950/30">
          <form
            onSubmit={handleConnectAndAnalyze}
            className="flex flex-col gap-3 md:flex-row md:items-end"
          >
            <div className="flex-1">
              <label className="mb-1 block text-xs font-semibold uppercase tracking-wider text-blue-400">
                Connect & Analyze GitHub Repository (FR-02 & FR-03)
              </label>
              <input
                type="text"
                value={newRepoInput}
                onChange={(e) => setNewRepoInput(e.target.value)}
                placeholder="https://github.com/owner/repository or owner/repository"
                className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3.5 py-2 text-sm text-white focus:border-blue-500 focus:outline-none"
              />
            </div>
            <div className="w-full md:w-36">
              <label className="mb-1 block text-xs font-medium text-slate-400">
                Branch
              </label>
              <input
                type="text"
                value={newRepoBranch}
                onChange={(e) => setNewRepoBranch(e.target.value)}
                className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-white focus:border-blue-500 focus:outline-none"
              />
            </div>
            <button
              type="submit"
              disabled={loading}
              className="flex items-center justify-center gap-2 rounded-lg bg-blue-600 px-5 py-2 text-sm font-semibold text-white transition hover:bg-blue-500 disabled:opacity-50"
            >
              {loading ? (
                <RefreshCw className="h-4 w-4 animate-spin" />
              ) : (
                <Plus className="h-4 w-4" />
              )}
              Import & Run AI Analysis
            </button>
          </form>
        </Card>

        {/* TAB 1: ANALYTICS DASHBOARD */}
        {activeTab === "dashboard" && (
          <section className="space-y-6">
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <Card>
                <div className="text-xs font-medium text-slate-400">
                  Average Health Score
                </div>
                <div className="mt-2 flex items-baseline justify-between">
                  <span className="text-3xl font-bold text-white">
                    {dashboard?.average_health_score ?? 0}%
                  </span>
                  <ScorePill score={dashboard?.average_health_score || 82.4} />
                </div>
              </Card>
              <Card>
                <div className="text-xs font-medium text-slate-400">
                  Code Quality Index
                </div>
                <div className="mt-2 flex items-baseline justify-between">
                  <span className="text-3xl font-bold text-emerald-400">
                    {dashboard?.average_quality_score ?? 0}%
                  </span>
                  <span className="text-xs text-slate-400">
                    {dashboard?.total_open_code_findings ?? 0} findings
                  </span>
                </div>
              </Card>
              <Card>
                <div className="text-xs font-medium text-slate-400">
                  Security Posture
                </div>
                <div className="mt-2 flex items-baseline justify-between">
                  <span className="text-3xl font-bold text-purple-400">
                    {dashboard?.average_security_score ?? 0}%
                  </span>
                  <span className="text-xs text-rose-400">
                    {dashboard?.total_open_security_findings ?? 0} alerts
                  </span>
                </div>
              </Card>
              <Card>
                <div className="text-xs font-medium text-slate-400">
                  Connected Repositories
                </div>
                <div className="mt-2 flex items-baseline justify-between">
                  <span className="text-3xl font-bold text-blue-400">
                    {dashboard?.total_repositories ?? 0}
                  </span>
                  <span className="text-xs text-slate-400">
                    {dashboard?.total_analyses ?? 0} total runs
                  </span>
                </div>
              </Card>
            </div>

            <ChartsSection dashboard={dashboard} />

            {/* Accessible Responsive Table (modern-web-guidance: responsive-table) */}
            <Card className="board-column">
              <div className="mb-4 flex items-center justify-between">
                <div>
                  <h2
                    id="repos-table-caption"
                    className="text-base font-semibold text-white"
                  >
                    Connected Repositories & Health Matrix
                  </h2>
                  <p className="text-xs text-slate-400">
                    Click Analyze or Inspect to view line-level AI code review and security findings
                  </p>
                </div>
              </div>

              <div
                tabIndex={0}
                role="region"
                aria-labelledby="repos-table-caption"
                className="table-wrapper"
              >
                <table>
                  <caption className="sr-only">
                    Connected GitHub repositories and latest AI analysis scores
                  </caption>
                  <thead>
                    <tr className="border-b border-slate-800 text-left text-xs uppercase tracking-wider text-slate-400">
                      <th className="px-4 py-3">Repository</th>
                      <th className="px-4 py-3">Branch</th>
                      <th className="px-4 py-3">Health Score</th>
                      <th className="px-4 py-3">Security Score</th>
                      <th className="px-4 py-3">Primary Language</th>
                      <th className="px-4 py-3">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/70 text-sm">
                    {repositories.length === 0 ? (
                      <tr>
                        <th className="px-4 py-4 font-medium text-slate-300">
                          No repositories connected yet
                        </th>
                        <td className="px-4 py-4 text-slate-400" colSpan={5}>
                          Use the bar above to import any GitHub repository and launch your first AI analysis.
                        </td>
                      </tr>
                    ) : (
                      repositories.map((repo) => (
                        <tr
                          key={repo.id}
                          className="transition hover:bg-slate-800/40"
                        >
                          <th className="px-4 py-3.5 font-semibold text-white">
                            {repo.full_name}
                          </th>
                          <td className="px-4 py-3.5 text-slate-300">
                            <code className="rounded bg-slate-800 px-2 py-0.5 text-xs">
                              {repo.default_branch}
                            </code>
                          </td>
                          <td className="px-4 py-3.5">
                            <ScorePill score={repo.latest_health_score} />
                          </td>
                          <td className="px-4 py-3.5">
                            <ScorePill score={repo.latest_security_score} />
                          </td>
                          <td className="px-4 py-3.5 text-slate-300">
                            {repo.primary_language || "Python"}
                          </td>
                          <td className="px-4 py-3.5">
                            <button
                              type="button"
                              onClick={() => handleRunAnalysisOnRepo(repo)}
                              disabled={loading}
                              className="inline-flex items-center gap-1.5 rounded-lg bg-blue-600/20 px-3 py-1.5 text-xs font-semibold text-blue-300 ring-1 ring-blue-500/30 hover:bg-blue-600 hover:text-white"
                            >
                              <Play className="h-3.5 w-3.5" />
                              Run Analysis
                            </button>
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </Card>
          </section>
        )}

        {/* TAB 2: REPOSITORIES & DEEP ANALYSIS WORKSPACE */}
        {activeTab === "repositories" && (
          <section className="space-y-6">
            {!activeResults ? (
              <Card>
                <p className="text-sm text-slate-300">
                  Select a repository below or click <strong>Import & Run AI Analysis</strong> above to inspect line-by-line Code Findings, Security Vulnerabilities, and AI Architecture Reports.
                </p>
                <div className="mt-4 flex flex-wrap gap-3">
                  {repositories.map((repo) => (
                    <button
                      key={repo.id}
                      type="button"
                      onClick={() => handleRunAnalysisOnRepo(repo)}
                      className="flex items-center gap-2 rounded-lg border border-slate-700 bg-slate-800 px-4 py-2 text-xs font-semibold text-white hover:border-blue-500"
                    >
                      <FolderGit2 className="h-4 w-4 text-blue-400" />
                      Analyze {repo.full_name}
                    </button>
                  ))}
                </div>
              </Card>
            ) : (
              <div className="space-y-6">
                <Card className="border-blue-500/30">
                  <div className="flex flex-wrap items-center justify-between gap-4">
                    <div>
                      <div className="flex items-center gap-2">
                        <h2 className="text-lg font-bold text-white">
                          {activeResults.repository.full_name}
                        </h2>
                        <ScorePill score={activeResults.job.health_score} />
                      </div>
                      <p className="mt-1 text-xs text-slate-300">
                        {activeResults.job.summary}
                      </p>
                    </div>
                    <button
                      type="button"
                      onClick={() =>
                        apiClient.downloadReportPdf(
                          token,
                          activeResults.job.id,
                          activeResults.repository.name
                        )
                      }
                      className="flex items-center gap-2 rounded-lg bg-emerald-600 px-4 py-2 text-xs font-semibold text-white hover:bg-emerald-500"
                    >
                      <Download className="h-4 w-4" />
                      Download PDF Report (FR-07)
                    </button>
                  </div>
                </Card>

                <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
                  {/* Security Vulnerability Findings (FR-04) */}
                  <Card className="board-column">
                    <div className="mb-4 flex items-center gap-2">
                      <ShieldAlert className="h-5 w-5 text-rose-400" />
                      <h3 className="text-base font-semibold text-white">
                        Security Vulnerabilities (
                        {activeResults.security_findings.length})
                      </h3>
                    </div>
                    <div className="space-y-3">
                      {activeResults.security_findings.map((sf) => (
                        <div
                          key={sf.id}
                          className="rounded-lg border border-slate-800 bg-slate-950/80 p-3.5"
                        >
                          <div className="flex items-center justify-between gap-2">
                            <span className="text-sm font-semibold text-white">
                              {sf.title}
                            </span>
                            <div className="flex items-center gap-1.5">
                              {(sf.cve_id || sf.cwe_id) && (
                                <span className="rounded bg-slate-800 px-2 py-0.5 text-[11px] font-mono text-slate-300">
                                  {sf.cve_id || sf.cwe_id}
                                </span>
                              )}
                              <SeverityBadge severity={sf.severity} />
                            </div>
                          </div>
                          <div className="mt-1 text-xs font-mono text-blue-400">
                            {sf.package_or_file}
                            {sf.line_number ? `:L${sf.line_number}` : ""}
                          </div>
                          <p className="mt-1.5 text-xs text-slate-300">
                            {sf.description}
                          </p>
                          <div className="mt-2 rounded border border-emerald-500/20 bg-emerald-500/5 p-2 text-xs text-emerald-300">
                            <strong>Recommendation:</strong> {sf.recommendation}
                          </div>
                        </div>
                      ))}
                    </div>
                  </Card>

                  {/* Code Quality & Bug Findings (FR-03) */}
                  <Card className="board-column">
                    <div className="mb-4 flex items-center gap-2">
                      <Code2 className="h-5 w-5 text-amber-400" />
                      <h3 className="text-base font-semibold text-white">
                        AI Code Review & Bug Findings (
                        {activeResults.code_findings.length})
                      </h3>
                    </div>
                    <div className="space-y-3">
                      {activeResults.code_findings.map((cf) => (
                        <div
                          key={cf.id}
                          className="rounded-lg border border-slate-800 bg-slate-950/80 p-3.5"
                        >
                          <div className="flex items-center justify-between gap-2">
                            <span className="text-sm font-semibold text-white">
                              {cf.title}
                            </span>
                            <SeverityBadge severity={cf.severity} />
                          </div>
                          <div className="mt-1 text-xs font-mono text-blue-400">
                            {cf.file_path}:L{cf.start_line}
                          </div>
                          <p className="mt-1.5 text-xs text-slate-300">
                            {cf.message}
                          </p>
                          {cf.suggested_fix && (
                            <div className="mt-2 rounded border border-blue-500/20 bg-blue-500/5 p-2 text-xs text-blue-300">
                              <strong>Suggested Fix:</strong> {cf.suggested_fix}
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  </Card>
                </div>

                {/* AI Generated Documentation & Architecture Sections (FR-05) */}
                <Card className="board-column">
                  <div className="mb-4 flex items-center gap-2">
                    <BookOpen className="h-5 w-5 text-blue-400" />
                    <h3 className="text-base font-semibold text-white">
                      AI-Generated Documentation & Architecture Reports
                    </h3>
                  </div>
                  <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                    {activeResults.ai_reports.map((sec) => (
                      <div
                        key={sec.id}
                        className="rounded-lg border border-slate-800 bg-slate-950 p-4"
                      >
                        <div className="mb-2 flex items-center justify-between">
                          <span className="text-sm font-bold text-white">
                            {sec.title}
                          </span>
                          <span className="rounded bg-blue-500/10 px-2 py-0.5 text-[11px] uppercase text-blue-400">
                            {sec.section_type}
                          </span>
                        </div>
                        <pre className="max-h-56 overflow-auto whitespace-pre-wrap font-mono text-xs text-slate-300">
                          {sec.markdown_content}
                        </pre>
                      </div>
                    ))}
                  </div>
                </Card>
              </div>
            )}
          </section>
        )}

        {/* TAB 3: GEMINI AI STUDIO (FR-03, FR-05) */}
        {activeTab === "ai-studio" && (
          <section className="space-y-6">
            <div className="flex flex-wrap gap-2">
              {(
                [
                  { id: "review", label: "AI Code Review (FR-03)" },
                  { id: "docs", label: "AI Documentation Generator (FR-05)" },
                  { id: "explain", label: "RAG Code Explainer (FR-03 / pgvector)" },
                ] as const
              ).map((tab) => (
                <button
                  key={tab.id}
                  type="button"
                  onClick={() => setStudioSubTab(tab.id)}
                  className={`rounded-lg px-4 py-2 text-xs font-semibold transition ${
                    studioSubTab === tab.id
                      ? "bg-blue-600 text-white"
                      : "border border-slate-800 bg-slate-900 text-slate-400 hover:text-white"
                  }`}
                >
                  {tab.label}
                </button>
              ))}
            </div>

            <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
              <Card className="space-y-4">
                <div className="flex items-center justify-between">
                  <h3 className="text-sm font-semibold text-white">
                    Source Code / Context Input
                  </h3>
                  <div className="flex items-center gap-3">
                    <select
                      value={snippetLang}
                      onChange={(e) => setSnippetLang(e.target.value)}
                      className="rounded border border-slate-700 bg-slate-950 px-2.5 py-1 text-xs text-white"
                    >
                      <option value="python">Python</option>
                      <option value="typescript">TypeScript</option>
                      <option value="javascript">JavaScript</option>
                      <option value="go">Go</option>
                    </select>
                    {studioSubTab === "review" && (
                      <label className="flex items-center gap-1.5 text-xs text-slate-300">
                        <input
                          type="checkbox"
                          checked={deepReasoning}
                          onChange={(e) => setDeepReasoning(e.target.checked)}
                        />
                        Gemini 4 Argon Deep Mode
                      </label>
                    )}
                  </div>
                </div>

                {studioSubTab === "docs" && (
                  <div className="grid grid-cols-2 gap-3">
                    <input
                      type="text"
                      value={docProjectName}
                      onChange={(e) => setDocProjectName(e.target.value)}
                      placeholder="Project Name"
                      className="rounded-lg border border-slate-700 bg-slate-950 px-3 py-1.5 text-xs text-white"
                    />
                    <select
                      value={docType}
                      onChange={(e) => setDocType(e.target.value)}
                      className="rounded-lg border border-slate-700 bg-slate-950 px-3 py-1.5 text-xs text-white"
                    >
                      <option value="readme">README.md</option>
                      <option value="architecture">Architecture Spec</option>
                      <option value="api_docs">API Documentation</option>
                    </select>
                  </div>
                )}

                {studioSubTab === "explain" && (
                  <input
                    type="text"
                    value={explainQuestion}
                    onChange={(e) => setExplainQuestion(e.target.value)}
                    placeholder="Ask a specific question about this code..."
                    className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-xs text-white"
                  />
                )}

                <textarea
                  rows={11}
                  value={snippetCode}
                  onChange={(e) => setSnippetCode(e.target.value)}
                  className="w-full rounded-lg border border-slate-700 bg-slate-950 p-3 font-mono text-xs text-slate-100 focus:border-blue-500 focus:outline-none"
                />

                <button
                  type="button"
                  disabled={loading}
                  onClick={async () => {
                    setLoading(true);
                    try {
                      if (studioSubTab === "review") {
                        const res = await apiClient.runCodeReview(
                          token,
                          snippetCode,
                          snippetLang,
                          `snippet.${snippetLang === "python" ? "py" : "ts"}`,
                          deepReasoning
                        );
                        setReviewOutput(res);
                      } else if (studioSubTab === "docs") {
                        const res = await apiClient.generateDocumentation(
                          token,
                          docProjectName,
                          snippetCode,
                          docType
                        );
                        setDocOutput(res);
                      } else {
                        const res = await apiClient.explainCode(
                          token,
                          snippetCode,
                          snippetLang,
                          explainQuestion,
                          repositories[0]?.id
                        );
                        setExplainOutput(res);
                      }
                    } catch (err) {
                      setErrorBanner(
                        err instanceof Error ? err.message : "AI call failed"
                      );
                    } finally {
                      setLoading(false);
                    }
                  }}
                  className="flex w-full items-center justify-center gap-2 rounded-lg bg-blue-600 px-4 py-2.5 text-xs font-semibold text-white hover:bg-blue-500"
                >
                  <Sparkles className="h-4 w-4" />
                  {studioSubTab === "review"
                    ? "Run Gemini AI Code Review"
                    : studioSubTab === "docs"
                    ? "Generate Technical Documentation"
                    : "Explain Code with RAG Context"}
                </button>
              </Card>

              <Card className="space-y-4">
                <h3 className="text-sm font-semibold text-white">
                  Gemini Intelligence Output
                </h3>
                {studioSubTab === "review" && reviewOutput && (
                  <div className="space-y-3 text-xs">
                    <div className="flex items-center justify-between">
                      <span className="font-semibold text-blue-400">
                        Model: {reviewOutput.model_used}
                      </span>
                      <ScorePill score={reviewOutput.quality_score} />
                    </div>
                    <p className="text-slate-300">{reviewOutput.summary}</p>
                    <div className="space-y-2">
                      {reviewOutput.findings.map((f, i) => (
                        <div
                          key={i}
                          className="rounded border border-slate-800 bg-slate-950 p-2.5"
                        >
                          <div className="flex items-center justify-between">
                            <span className="font-semibold text-white">
                              L{f.line}: {f.title}
                            </span>
                            <SeverityBadge severity={f.severity} />
                          </div>
                          <p className="mt-1 text-slate-400">{f.message}</p>
                          <p className="mt-1 text-emerald-400">
                            Fix: {f.suggested_fix}
                          </p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {studioSubTab === "docs" && docOutput && (
                  <div className="space-y-3 text-xs">
                    <div className="font-semibold text-blue-400">
                      {docOutput.title} ({docOutput.model_used})
                    </div>
                    <pre className="max-h-80 overflow-auto whitespace-pre-wrap rounded border border-slate-800 bg-slate-950 p-3 font-mono text-slate-200">
                      {docOutput.markdown_content}
                    </pre>
                  </div>
                )}

                {studioSubTab === "explain" && explainOutput && (
                  <div className="space-y-3 text-xs">
                    <p className="text-slate-200">{explainOutput.summary}</p>
                    <div className="rounded border border-blue-500/20 bg-blue-500/5 p-2.5 text-blue-300">
                      {explainOutput.complexity_analysis}
                    </div>
                    <ul className="space-y-1.5 text-slate-300">
                      {explainOutput.step_by_step_explanation.map((step, i) => (
                        <li key={i}>• {step}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </Card>
            </div>
          </section>
        )}

        {/* TAB 4: REPORTS & PDF DOWNLOAD (FR-07) */}
        {activeTab === "reports" && (
          <section className="space-y-4">
            <Card className="board-column">
              <h2
                id="reports-table-caption"
                className="mb-1 text-base font-semibold text-white"
              >
                Analysis History & Downloadable PDF Reports (FR-07)
              </h2>
              <p className="mb-4 text-xs text-slate-400">
                Review historical repository evaluations or export executive & technical PDF reports
              </p>

              <div
                tabIndex={0}
                role="region"
                aria-labelledby="reports-table-caption"
                className="table-wrapper"
              >
                <table>
                  <caption className="sr-only">
                    Generated repository analysis reports and PDF downloads
                  </caption>
                  <thead>
                    <tr className="border-b border-slate-800 text-left text-xs uppercase tracking-wider text-slate-400">
                      <th className="px-4 py-3">Repository</th>
                      <th className="px-4 py-3">Branch / Commit</th>
                      <th className="px-4 py-3">Health Score</th>
                      <th className="px-4 py-3">Security Score</th>
                      <th className="px-4 py-3">Findings</th>
                      <th className="px-4 py-3">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/70 text-sm">
                    {reports.length === 0 ? (
                      <tr>
                        <th className="px-4 py-4 text-slate-300">
                          No reports generated yet
                        </th>
                        <td className="px-4 py-4 text-slate-400" colSpan={5}>
                          Run a repository analysis to generate your first downloadable PDF report.
                        </td>
                      </tr>
                    ) : (
                      reports.map((rep) => (
                        <tr
                          key={rep.id}
                          className="transition hover:bg-slate-800/40"
                        >
                          <th className="px-4 py-3.5 font-semibold text-white">
                            {rep.repository_name}
                          </th>
                          <td className="px-4 py-3.5 text-xs text-slate-300">
                            {rep.branch} ({rep.commit_sha.slice(0, 7)})
                          </td>
                          <td className="px-4 py-3.5">
                            <ScorePill score={rep.health_score} />
                          </td>
                          <td className="px-4 py-3.5">
                            <ScorePill score={rep.security_score} />
                          </td>
                          <td className="px-4 py-3.5 text-xs text-slate-300">
                            {rep.code_findings_count} code /{" "}
                            {rep.security_findings_count} security
                          </td>
                          <td className="px-4 py-3.5">
                            <div className="flex items-center gap-2">
                              <button
                                type="button"
                                onClick={() => handleInspectReport(rep.id)}
                                className="rounded-lg border border-slate-700 bg-slate-800 px-2.5 py-1 text-xs font-medium text-slate-200 hover:border-blue-500"
                              >
                                Inspect
                              </button>
                              <button
                                type="button"
                                onClick={() =>
                                  apiClient.downloadReportPdf(
                                    token,
                                    rep.id,
                                    rep.repository_name
                                  )
                                }
                                className="inline-flex items-center gap-1 rounded-lg bg-emerald-600/20 px-2.5 py-1 text-xs font-semibold text-emerald-300 ring-1 ring-emerald-500/30 hover:bg-emerald-600 hover:text-white"
                              >
                                <Download className="h-3.5 w-3.5" />
                                PDF
                              </button>
                            </div>
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </Card>
          </section>
        )}
      </main>
    </div>
  );
}


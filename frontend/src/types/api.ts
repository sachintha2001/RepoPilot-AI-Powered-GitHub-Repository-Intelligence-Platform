export interface UserProfile {
  id: string;
  email: string;
  full_name: string;
  role: string;
  avatar_url?: string | null;
  created_at: string;
  github_connected: boolean;
  github_username?: string | null;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  user: UserProfile;
}

export interface Repository {
  id: string;
  user_id: string;
  github_repo_id?: number | null;
  name: string;
  full_name: string;
  description?: string | null;
  html_url: string;
  default_branch: string;
  is_private: boolean;
  primary_language?: string | null;
  language_distribution: Record<string, number>;
  stars_count: number;
  forks_count: number;
  latest_health_score?: number | null;
  latest_quality_score?: number | null;
  latest_security_score?: number | null;
  last_analyzed_at?: string | null;
  created_at: string;
}

export interface AnalysisStatus {
  id: string;
  repository_id: string;
  commit_sha: string;
  branch: string;
  status: "queued" | "in_progress" | "completed" | "failed" | string;
  progress_percent: number;
  current_step: string;
  health_score?: number | null;
  code_quality_score?: number | null;
  security_score?: number | null;
  maintainability_score?: number | null;
  summary?: string | null;
  error_message?: string | null;
  started_at: string;
  completed_at?: string | null;
}

export interface CodeFinding {
  id: string;
  job_id: string;
  file_path: string;
  start_line: number;
  end_line: number;
  severity: "info" | "warning" | "error" | "critical" | string;
  category: string;
  title: string;
  message: string;
  suggested_fix?: string | null;
  code_snippet?: string | null;
}

export interface SecurityFinding {
  id: string;
  job_id: string;
  finding_type: string;
  severity: "low" | "medium" | "high" | "critical" | string;
  package_or_file: string;
  line_number?: number | null;
  cve_id?: string | null;
  cwe_id?: string | null;
  title: string;
  description: string;
  recommendation: string;
}

export interface AIReportSection {
  id: string;
  job_id: string;
  section_type: string;
  title: string;
  markdown_content: string;
  structured_metadata: Record<string, unknown>;
  created_at: string;
}

export interface AnalysisResults {
  job: AnalysisStatus;
  repository: Repository;
  code_findings: CodeFinding[];
  security_findings: SecurityFinding[];
  ai_reports: AIReportSection[];
}

export interface AnalysisHistoryItem {
  id: string;
  repository_id: string;
  job_id: string;
  commit_sha: string;
  health_score: number;
  code_quality_score: number;
  security_score: number;
  maintainability_score: number;
  total_code_findings: number;
  total_security_findings: number;
  recorded_at: string;
}

export interface DashboardOverview {
  total_repositories: number;
  total_analyses: number;
  average_health_score: number;
  average_quality_score: number;
  average_security_score: number;
  total_open_code_findings: number;
  total_open_security_findings: number;
  language_distribution: Record<string, number>;
  severity_breakdown: Record<string, number>;
  recent_history: AnalysisHistoryItem[];
  recent_jobs: AnalysisStatus[];
}

export interface ReportSummaryItem {
  id: string;
  job_id: string;
  repository_id: string;
  repository_name: string;
  branch: string;
  commit_sha: string;
  status: string;
  health_score?: number | null;
  code_quality_score?: number | null;
  security_score?: number | null;
  maintainability_score?: number | null;
  summary?: string | null;
  code_findings_count: number;
  security_findings_count: number;
  sections_count: number;
  created_at: string;
  completed_at?: string | null;
}


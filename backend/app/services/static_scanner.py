import ast
import json
import re
from typing import Any, Dict, List


KNOWN_VULNERABLE_PACKAGES: Dict[str, Dict[str, str]] = {
    "requests": {
        "vulnerable_prefix": "2.25",
        "cve": "CVE-2023-32681",
        "severity": "medium",
        "description": "Unintended leak of Proxy-Authorization header in requests prior to 2.31.0.",
        "recommendation": "Upgrade `requests` to `>=2.31.0` in requirements.txt.",
    },
    "pyyaml": {
        "vulnerable_prefix": "5.3",
        "cve": "CVE-2020-14343",
        "severity": "critical",
        "description": "Arbitrary code execution in PyYAML via full_load / UnsafeLoader.",
        "recommendation": "Upgrade `pyyaml` to `>=6.0.1` and always use `yaml.safe_load()`.",
    },
    "cryptography": {
        "vulnerable_prefix": "38.",
        "cve": "CVE-2023-23931",
        "severity": "high",
        "description": "Memory corruption in Cipher.update_into when passed immutable buffers.",
        "recommendation": "Upgrade `cryptography` to `>=42.0.0`.",
    },
    "lodash": {
        "vulnerable_prefix": "4.17.15",
        "cve": "CVE-2021-23337",
        "severity": "high",
        "description": "Command injection via template function in lodash < 4.17.21.",
        "recommendation": "Upgrade `lodash` to `>=4.17.21` in package.json.",
    },
    "axios": {
        "vulnerable_prefix": "0.21",
        "cve": "CVE-2023-45857",
        "severity": "medium",
        "description": "CSRF token leakage in axios versions before 1.6.0.",
        "recommendation": "Upgrade `axios` to `>=1.6.0`.",
    },
}


class StaticAnalysisScanner:
    """Performs AST and pattern-based static code quality and security scanning."""

    @classmethod
    def scan_repository_files(
        cls, files: Dict[str, str]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Run code quality and security checks across all repository files."""
        code_findings: List[Dict[str, Any]] = []
        security_findings: List[Dict[str, Any]] = []

        for file_path, content in files.items():
            lower_path = file_path.lower()
            if lower_path.endswith("requirements.txt"):
                security_findings.extend(
                    cls._scan_requirements_txt(file_path, content)
                )
            elif lower_path.endswith("package.json"):
                security_findings.extend(cls._scan_package_json(file_path, content))

            if lower_path.endswith(".py"):
                c_finds, s_finds = cls._scan_python_file(file_path, content)
                code_findings.extend(c_finds)
                security_findings.extend(s_finds)
            elif lower_path.endswith((".ts", ".tsx", ".js", ".jsx")):
                c_finds, s_finds = cls._scan_ts_js_file(file_path, content)
                code_findings.extend(c_finds)
                security_findings.extend(s_finds)

            # Universal secret & pattern scan
            security_findings.extend(cls._scan_secrets(file_path, content))

        return {
            "code_findings": code_findings,
            "security_findings": security_findings,
        }

    @classmethod
    def _scan_requirements_txt(
        cls, file_path: str, content: str
    ) -> List[Dict[str, Any]]:
        findings: List[Dict[str, Any]] = []
        for idx, raw_line in enumerate(content.splitlines(), start=1):
            line = raw_line.strip()
            if not line or line.startswith("#") or "==" not in line:
                continue
            pkg, version = [part.strip().lower() for part in line.split("==", 1)]
            vuln = KNOWN_VULNERABLE_PACKAGES.get(pkg)
            if vuln and version.startswith(vuln["vulnerable_prefix"]):
                findings.append(
                    {
                        "finding_type": "dependency",
                        "severity": vuln["severity"],
                        "package_or_file": f"{file_path} ({pkg}=={version})",
                        "line_number": idx,
                        "cve_id": vuln["cve"],
                        "cwe_id": "CWE-1395",
                        "title": f"Vulnerable Dependency: {pkg}=={version}",
                        "description": vuln["description"],
                        "recommendation": vuln["recommendation"],
                    }
                )
        return findings

    @classmethod
    def _scan_package_json(cls, file_path: str, content: str) -> List[Dict[str, Any]]:
        findings: List[Dict[str, Any]] = []
        try:
            data = json.loads(content)
            deps = {
                **data.get("dependencies", {}),
                **data.get("devDependencies", {}),
            }
            for pkg, ver in deps.items():
                clean_ver = str(ver).lstrip("^~")
                vuln = KNOWN_VULNERABLE_PACKAGES.get(pkg.lower())
                if vuln and clean_ver.startswith(vuln["vulnerable_prefix"]):
                    findings.append(
                        {
                            "finding_type": "dependency",
                            "severity": vuln["severity"],
                            "package_or_file": f"{file_path} ({pkg}@{clean_ver})",
                            "line_number": 1,
                            "cve_id": vuln["cve"],
                            "cwe_id": "CWE-1395",
                            "title": f"Vulnerable NPM Package: {pkg}@{clean_ver}",
                            "description": vuln["description"],
                            "recommendation": vuln["recommendation"],
                        }
                    )
        except Exception:
            pass
        return findings

    @classmethod
    def _scan_secrets(cls, file_path: str, content: str) -> List[Dict[str, Any]]:
        findings: List[Dict[str, Any]] = []
        secret_patterns = [
            (
                re.compile(r"AKIA[0-9A-Z]{16}"),
                "Hardcoded AWS Access Key ID",
                "critical",
                "CWE-798",
                "Rotate the exposed AWS key immediately and load credentials from IAM roles or environment variables.",
            ),
            (
                re.compile(
                    r"(?i)(api_key|secret_key|access_token|private_key)\s*=\s*['\"][A-Za-z0-9_\-]{14,}['\"]"
                ),
                "Hardcoded Secret or API Token in Source",
                "high",
                "CWE-798",
                "Move secrets out of source code into environment variables (`os.getenv`) or a secret manager.",
            ),
        ]
        for idx, line in enumerate(content.splitlines(), start=1):
            for pattern, title, severity, cwe, rec in secret_patterns:
                if pattern.search(line):
                    findings.append(
                        {
                            "finding_type": "secret",
                            "severity": severity,
                            "package_or_file": file_path,
                            "line_number": idx,
                            "cve_id": None,
                            "cwe_id": cwe,
                            "title": title,
                            "description": f"Detected potential hardcoded credential on line {idx} of `{file_path}`.",
                            "recommendation": rec,
                        }
                    )
        return findings

    @classmethod
    def _scan_python_file(
        cls, file_path: str, content: str
    ) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        code_findings: List[Dict[str, Any]] = []
        security_findings: List[Dict[str, Any]] = []
        lines = content.splitlines()

        try:
            tree = ast.parse(content)
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    # Mutable default arguments
                    for default in node.args.defaults:
                        if isinstance(default, (ast.List, ast.Dict, ast.Set)):
                            code_findings.append(
                                {
                                    "file_path": file_path,
                                    "start_line": node.lineno,
                                    "end_line": getattr(node, "end_lineno", node.lineno),
                                    "severity": "error",
                                    "category": "bug",
                                    "title": f"Mutable Default Argument in `{node.name}`",
                                    "message": (
                                        f"Function `{node.name}` uses a mutable literal (`list`, `dict`, or `set`) "
                                        "as a default parameter value, which persists state across calls."
                                    ),
                                    "suggested_fix": "Default the parameter to `None` and initialize inside the function body.",
                                    "code_snippet": lines[node.lineno - 1]
                                    if node.lineno <= len(lines)
                                    else "",
                                }
                            )
                    # Function length check
                    end_lineno = getattr(node, "end_lineno", node.lineno)
                    if (end_lineno - node.lineno) > 45:
                        code_findings.append(
                            {
                                "file_path": file_path,
                                "start_line": node.lineno,
                                "end_line": end_lineno,
                                "severity": "warning",
                                "category": "complexity",
                                "title": f"High Function Complexity in `{node.name}`",
                                "message": f"`{node.name}` spans {end_lineno - node.lineno} lines. Consider decomposing into smaller cohesive helpers.",
                                "suggested_fix": "Extract single-responsibility helper functions to improve testability.",
                                "code_snippet": lines[node.lineno - 1]
                                if node.lineno <= len(lines)
                                else "",
                            }
                        )
                elif isinstance(node, ast.ExceptHandler) and node.type is None:
                    code_findings.append(
                        {
                            "file_path": file_path,
                            "start_line": node.lineno,
                            "end_line": getattr(node, "end_lineno", node.lineno),
                            "severity": "warning",
                            "category": "bug",
                            "title": "Bare `except:` Clause Swallows System Exceptions",
                            "message": "Using a bare `except:` catches `SystemExit`, `KeyboardInterrupt`, and hides unexpected runtime errors.",
                            "suggested_fix": "Catch specific exceptions (e.g., `except ValueError as exc:`) and log the traceback.",
                            "code_snippet": lines[node.lineno - 1]
                            if node.lineno <= len(lines)
                            else "except:",
                        }
                    )
        except SyntaxError:
            pass

        for idx, line in enumerate(lines, start=1):
            if "hashlib.md5(" in line or "hashlib.sha1(" in line:
                security_findings.append(
                    {
                        "finding_type": "sast_pattern",
                        "severity": "high",
                        "package_or_file": file_path,
                        "line_number": idx,
                        "cve_id": None,
                        "cwe_id": "CWE-328",
                        "title": "Weak Cryptographic Hash (MD5/SHA1)",
                        "description": f"Line {idx} uses a collision-prone cryptographic hash algorithm unsuitable for passwords or sensitive digests.",
                        "recommendation": "Use Argon2, bcrypt, or `hashlib.pbkdf2_hmac('sha256', ...)` with a cryptographic salt.",
                    }
                )
            if "shell=True" in line and "subprocess" in content:
                security_findings.append(
                    {
                        "finding_type": "sast_pattern",
                        "severity": "critical",
                        "package_or_file": file_path,
                        "line_number": idx,
                        "cve_id": None,
                        "cwe_id": "CWE-78",
                        "title": "OS Command Injection Risk (`shell=True`)",
                        "description": f"Line {idx} invokes a subprocess with `shell=True`, enabling arbitrary shell command injection if user input is interpolated.",
                        "recommendation": "Pass command arguments as a list `['cmd', arg1]` with `shell=False`.",
                    }
                )
            if re.search(r"(?i)SELECT\s+.*\s+FROM\s+.*\{.*\}", line):
                security_findings.append(
                    {
                        "finding_type": "sast_pattern",
                        "severity": "critical",
                        "package_or_file": file_path,
                        "line_number": idx,
                        "cve_id": None,
                        "cwe_id": "CWE-89",
                        "title": "SQL Injection via String Formatting",
                        "description": f"Line {idx} constructs a SQL query using string interpolation (`f-string`), exposing the database to SQL injection.",
                        "recommendation": "Use parameterized queries (`cursor.execute('SELECT ... WHERE col = ?', (val,))`) or SQLAlchemy bound parameters.",
                    }
                )

        return code_findings, security_findings

    @classmethod
    def _scan_ts_js_file(
        cls, file_path: str, content: str
    ) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        code_findings: List[Dict[str, Any]] = []
        security_findings: List[Dict[str, Any]] = []
        for idx, line in enumerate(content.splitlines(), start=1):
            if "eval(" in line:
                security_findings.append(
                    {
                        "finding_type": "sast_pattern",
                        "severity": "critical",
                        "package_or_file": file_path,
                        "line_number": idx,
                        "cve_id": None,
                        "cwe_id": "CWE-95",
                        "title": "Dynamic Code Execution via `eval()`",
                        "description": f"Line {idx} executes dynamic JavaScript/TypeScript strings with `eval()`, creating a remote code execution / XSS vector.",
                        "recommendation": "Replace `eval()` with strict JSON parsing or a safe expression parser.",
                    }
                )
            if ": any" in line:
                code_findings.append(
                    {
                        "file_path": file_path,
                        "start_line": idx,
                        "end_line": idx,
                        "severity": "info",
                        "category": "maintainability",
                        "title": "Explicit `any` Type Disables TypeScript Type Safety",
                        "message": f"Line {idx} uses `: any`, bypassing compile-time type checking.",
                        "suggested_fix": "Define a strict TypeScript `interface` or `type` for the payload.",
                        "code_snippet": line.strip(),
                    }
                )
        return code_findings, security_findings


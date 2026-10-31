from datetime import datetime, timezone
from typing import Any, Dict, List


def _escape_pdf_text(text: str) -> str:
    """Escape characters special to PDF string literals and strip non-ASCII characters."""
    ascii_text = text.encode("ascii", errors="replace").decode("ascii")
    return (
        ascii_text.replace("\\", "\\\\")
        .replace("(", "\\(")
        .replace(")", "\\)")
    )


class PDFReportGenerator:
    """Generates standards-compliant PDF reports (%PDF-1.4) for repository analysis runs."""

    @classmethod
    def generate_analysis_pdf(
        cls,
        repo_name: str,
        job_data: Dict[str, Any],
        code_findings: List[Dict[str, Any]],
        security_findings: List[Dict[str, Any]],
        ai_reports: List[Dict[str, Any]],
    ) -> bytes:
        """Render a multi-page PDF document containing scores, findings, and AI insights."""
        lines: List[str] = [
            f"REPOPILOT - AI REPOSITORY INTELLIGENCE REPORT",
            f"Repository: {repo_name}",
            f"Generated At: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
            f"Analysis Job ID: {job_data.get('id', 'N/A')} | Branch: {job_data.get('branch', 'main')} | Status: {job_data.get('status', 'completed')}",
            "-" * 85,
            "1. EXECUTIVE HEALTH & QUALITY SCORES",
            f"   * Overall Repository Health Score : {job_data.get('health_score', 0.0)} / 100",
            f"   * Code Quality Score              : {job_data.get('code_quality_score', 0.0)} / 100",
            f"   * Security Posture Score          : {job_data.get('security_score', 0.0)} / 100",
            f"   * Maintainability Index           : {job_data.get('maintainability_score', 0.0)} / 100",
            "",
            f"   Executive Summary: {job_data.get('summary') or 'Automated static, security, and Gemini AI analysis completed.'}",
            "-" * 85,
            f"2. SECURITY VULNERABILITY FINDINGS ({len(security_findings)} detected)",
        ]

        if not security_findings:
            lines.append("   No security vulnerabilities identified.")
        else:
            for idx, sf in enumerate(security_findings[:15], start=1):
                cve_badge = f" [{sf.get('cve_id') or sf.get('cwe_id')}]" if (sf.get("cve_id") or sf.get("cwe_id")) else ""
                lines.append(
                    f"   [{idx}] ({sf.get('severity', 'medium').upper()}){cve_badge} {sf.get('title', 'Security Issue')}"
                )
                lines.append(f"       Target: {sf.get('package_or_file', '')}")
                lines.append(f"       Fix   : {sf.get('recommendation', '')[:100]}")

        lines.append("-" * 85)
        lines.append(f"3. CODE QUALITY & BUG FINDINGS ({len(code_findings)} detected)")
        if not code_findings:
            lines.append("   No code quality issues identified.")
        else:
            for idx, cf in enumerate(code_findings[:15], start=1):
                lines.append(
                    f"   [{idx}] ({cf.get('severity', 'warning').upper()} | {cf.get('category', 'code')}) {cf.get('title', '')}"
                )
                lines.append(
                    f"       Location: {cf.get('file_path', '')}:L{cf.get('start_line', 1)}"
                )
                if cf.get("suggested_fix"):
                    lines.append(f"       Fix     : {cf.get('suggested_fix', '')[:100]}")

        lines.append("-" * 85)
        lines.append("4. AI ARCHITECTURAL & DOCUMENTATION INSIGHTS")
        for rep in ai_reports[:4]:
            lines.append(f"   [{rep.get('section_type', 'report').upper()}] {rep.get('title', '')}")
            snippet = " ".join(rep.get("markdown_content", "").splitlines())[:180]
            lines.append(f"       {snippet}...")

        # Paginate at 44 lines per page
        page_chunks: List[List[str]] = [
            lines[i : i + 44] for i in range(0, len(lines), 44)
        ] or [["RepoPilot Report"]]

        objects: List[bytes] = []

        # Obj 1: Catalog, Obj 2: Pages, Obj 3: Font
        page_obj_ids = []
        content_obj_ids = []
        next_id = 4
        for _ in page_chunks:
            page_obj_ids.append(next_id)
            content_obj_ids.append(next_id + 1)
            next_id += 2

        kids_str = " ".join(f"{pid} 0 R" for pid in page_obj_ids)
        objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
        objects.append(
            f"<< /Type /Pages /Kids [{kids_str}] /Count {len(page_obj_ids)} >>".encode(
                "ascii"
            )
        )
        objects.append(
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Courier >>"
        )

        for chunk_lines, page_id, content_id in zip(
            page_chunks, page_obj_ids, content_obj_ids
        ):
            stream_commands = ["BT", "/F1 9 Tf", "40 750 Td", "14 TL"]
            for line in chunk_lines:
                stream_commands.append(f"({_escape_pdf_text(line[:105])}) Tj T*")
            stream_commands.append("ET")
            stream_bytes = "\n".join(stream_commands).encode("ascii")

            page_dict = (
                f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
                f"/Resources << /Font << /F1 3 0 R >> >> /Contents {content_id} 0 R >>"
            ).encode("ascii")
            content_dict = (
                f"<< /Length {len(stream_bytes)} >>\nstream\n".encode("ascii")
                + stream_bytes
                + b"\nendstream"
            )
            objects.append(page_dict)
            objects.append(content_dict)

        # Assemble PDF with xref table
        out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
        offsets: List[int] = [0]
        for idx, obj_bytes in enumerate(objects, start=1):
            offsets.append(len(out))
            out.extend(f"{idx} 0 obj\n".encode("ascii"))
            out.extend(obj_bytes)
            out.extend(b"\nendobj\n")

        xref_offset = len(out)
        out.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
        out.extend(b"0000000000 65535 f \n")
        for off in offsets[1:]:
            out.extend(f"{off:010d} 00000 n \n".encode("ascii"))

        out.extend(
            (
                f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
                f"startxref\n{xref_offset}\n%%EOF\n"
            ).encode("ascii")
        )
        return bytes(out)


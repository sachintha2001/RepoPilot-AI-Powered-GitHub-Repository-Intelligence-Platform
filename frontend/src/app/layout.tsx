import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "RepoPilot – AI-Powered GitHub Repository Intelligence Platform",
  description:
    "Analyze GitHub repositories with Google Gemini AI, LangGraph workflows, pgvector RAG, static code review, and dependency security scanning.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen bg-slate-950 text-slate-100 antialiased">
        {children}
      </body>
    </html>
  );
}


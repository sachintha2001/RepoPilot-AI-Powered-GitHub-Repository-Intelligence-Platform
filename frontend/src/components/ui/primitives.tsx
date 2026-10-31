import React from "react";

export function Card({
  children,
  className = "",
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={`rounded-xl border border-slate-800 bg-slate-900/80 p-5 shadow-lg backdrop-blur-sm ${className}`}
    >
      {children}
    </div>
  );
}

export function SeverityBadge({ severity }: { severity: string }) {
  const normalized = (severity || "info").toLowerCase();
  const styles: Record<string, string> = {
    critical: "bg-red-500/15 text-red-400 border-red-500/30",
    high: "bg-orange-500/15 text-orange-400 border-orange-500/30",
    error: "bg-rose-500/15 text-rose-400 border-rose-500/30",
    medium: "bg-amber-500/15 text-amber-300 border-amber-500/30",
    warning: "bg-amber-500/15 text-amber-300 border-amber-500/30",
    low: "bg-sky-500/15 text-sky-400 border-sky-500/30",
    info: "bg-indigo-500/15 text-indigo-300 border-indigo-500/30",
  };
  return (
    <span
      className={`inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-semibold uppercase tracking-wide ${
        styles[normalized] || styles.info
      }`}
    >
      {normalized}
    </span>
  );
}

export function ScorePill({ score }: { score?: number | null }) {
  if (score === undefined || score === null) {
    return <span className="text-xs text-slate-400">Not analyzed</span>;
  }
  const color =
    score >= 80
      ? "text-emerald-400 bg-emerald-500/10 border-emerald-500/30"
      : score >= 60
      ? "text-amber-300 bg-amber-500/10 border-amber-500/30"
      : "text-rose-400 bg-rose-500/10 border-rose-500/30";
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-bold ${color}`}
    >
      {score.toFixed(1)} / 100
    </span>
  );
}


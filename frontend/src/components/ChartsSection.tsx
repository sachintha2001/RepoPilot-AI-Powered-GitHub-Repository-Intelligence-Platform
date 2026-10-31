"use client";

import React from "react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { DashboardOverview } from "@/types/api";
import { Card } from "@/components/ui/primitives";

const LANGUAGE_COLORS = [
  "#3b82f6",
  "#10b981",
  "#8b5cf6",
  "#f59e0b",
  "#ec4899",
  "#06b6d4",
];

export function ChartsSection({
  dashboard,
}: {
  dashboard: DashboardOverview | null;
}) {
  const historyData =
    dashboard?.recent_history && dashboard.recent_history.length > 0
      ? [...dashboard.recent_history]
          .reverse()
          .map((item, idx) => ({
            run: `Run #${idx + 1}`,
            health: item.health_score,
            quality: item.code_quality_score,
            security: item.security_score,
          }))
      : [
          { run: "Run #1", health: 68, quality: 72, security: 62 },
          { run: "Run #2", health: 74, quality: 78, security: 70 },
          { run: "Run #3", health: 83, quality: 86, security: 80 },
        ];

  const langEntries = Object.entries(
    dashboard?.language_distribution || {
      Python: 64.2,
      TypeScript: 28.3,
      Markdown: 7.5,
    }
  ).map(([name, value]) => ({ name, value }));

  const severityEntries = Object.entries(
    dashboard?.severity_breakdown || {
      critical: 2,
      high: 3,
      medium: 2,
      warning: 3,
      info: 1,
    }
  ).map(([severity, count]) => ({
    severity: severity.toUpperCase(),
    count,
  }));

  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
      <Card className="board-column lg:col-span-2">
        <div className="mb-4 flex items-center justify-between">
          <div>
            <h3 className="text-base font-semibold text-white">
              Repository Health & Security Trajectory
            </h3>
            <p className="text-xs text-slate-400">
              Historical score progression across analysis runs (FR-06 & FR-07)
            </p>
          </div>
        </div>
        <div className="h-64 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={historyData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
              <XAxis dataKey="run" stroke="#94a3b8" fontSize={12} />
              <YAxis domain={[0, 100]} stroke="#94a3b8" fontSize={12} />
              <Tooltip
                contentStyle={{
                  backgroundColor: "#0f172a",
                  borderColor: "#334155",
                  borderRadius: "0.5rem",
                }}
              />
              <Legend />
              <Area
                type="monotone"
                dataKey="health"
                name="Health Score"
                stroke="#3b82f6"
                fill="#3b82f6"
                fillOpacity={0.2}
              />
              <Area
                type="monotone"
                dataKey="quality"
                name="Code Quality"
                stroke="#10b981"
                fill="#10b981"
                fillOpacity={0.15}
              />
              <Area
                type="monotone"
                dataKey="security"
                name="Security Posture"
                stroke="#8b5cf6"
                fill="#8b5cf6"
                fillOpacity={0.15}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </Card>

      <Card className="board-column">
        <h3 className="text-base font-semibold text-white">
          Language Distribution
        </h3>
        <p className="mb-3 text-xs text-slate-400">
          Aggregated across connected repositories
        </p>
        <div className="h-64 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={langEntries}
                dataKey="value"
                nameKey="name"
                cx="50%"
                cy="50%"
                innerRadius={52}
                outerRadius={82}
                paddingAngle={3}
              >
                {langEntries.map((entry, index) => (
                  <Cell
                    key={entry.name}
                    fill={LANGUAGE_COLORS[index % LANGUAGE_COLORS.length]}
                  />
                ))}
              </Pie>
              <Tooltip
                contentStyle={{
                  backgroundColor: "#0f172a",
                  borderColor: "#334155",
                  borderRadius: "0.5rem",
                }}
              />
              <Legend />
            </PieChart>
          </ResponsiveContainer>
        </div>
      </Card>

      <Card className="board-column lg:col-span-3">
        <h3 className="text-base font-semibold text-white">
          Code & Security Findings by Severity
        </h3>
        <p className="mb-3 text-xs text-slate-400">
          Distribution of static analysis, dependency CVE, and SAST findings
        </p>
        <div className="h-52 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={severityEntries}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
              <XAxis dataKey="severity" stroke="#94a3b8" fontSize={12} />
              <YAxis stroke="#94a3b8" fontSize={12} allowDecimals={false} />
              <Tooltip
                contentStyle={{
                  backgroundColor: "#0f172a",
                  borderColor: "#334155",
                  borderRadius: "0.5rem",
                }}
              />
              <Bar dataKey="count" name="Findings Count" fill="#f59e0b" radius={[6, 6, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </Card>
    </div>
  );
}


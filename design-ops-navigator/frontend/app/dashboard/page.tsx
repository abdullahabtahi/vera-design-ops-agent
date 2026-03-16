"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  BarChart2, AlertTriangle, CheckCircle, Layers, ArrowRight,
  ChevronRight, Flame, TrendingUp, TrendingDown, Minus,
  Activity, Clock, Target, Sparkles,
} from "lucide-react";
import { loadSessions, loadMessages } from "../hooks/useAgentStream";
import { getEvalScores, type EvalScores } from "../../lib/api";

// ── Types ─────────────────────────────────────────────────────────────────────

interface RawIssue {
  severity: string;
  rule_citation: string;
  element?: string;
  description?: string;
}

interface SessionStat {
  id: string;
  title: string;
  updatedAt: string;
  score: number;
  grade: string;
  ringColor: string;
  issueCount: number;
  criticalCount: number;
  highCount: number;
}

interface OpenIssue {
  sessionId: string;
  sessionTitle: string;
  element: string;
  description: string;
  severity: string;
  citation: string;
}

interface DashboardData {
  healthScore: number;
  grade: string;
  gradeColor: string;
  ringColor: string;
  totalSessions: number;
  critiqueSessions: number;
  totalIssues: number;
  openUrgent: number;
  fixRate: number;
  trend: "up" | "down" | "flat";
  bySeverity: { critical: number; high: number; medium: number; low: number };
  byStatus: { open: number; fixed: number; in_progress: number; wont_fix: number };
  byCategory: { name: string; count: number; bar: string; label: string }[];
  sessionStats: SessionStat[];
  topOpenIssues: OpenIssue[];
}

// ── Constants ─────────────────────────────────────────────────────────────────

const SEV_ORDER: Record<string, number> = { critical: 0, high: 1, medium: 2, low: 3 };

const CAT_CFG: Record<string, { bar: string; label: string }> = {
  WCAG:      { bar: "bg-blue-500",    label: "text-blue-400" },
  Nielsen:   { bar: "bg-indigo-500",  label: "text-indigo-400" },
  Gestalt:   { bar: "bg-violet-500",  label: "text-violet-400" },
  Cognitive: { bar: "bg-amber-500",   label: "text-amber-400" },
  Material:  { bar: "bg-emerald-500", label: "text-emerald-400" },
  Other:     { bar: "bg-zinc-500",    label: "text-zinc-400" },
};

function categorize(c: string): string {
  const s = c.toLowerCase();
  if (s.includes("wcag")) return "WCAG";
  if (s.includes("nielsen") || s.includes("heuristic")) return "Nielsen";
  if (s.includes("gestalt")) return "Gestalt";
  if (s.includes("fitts") || s.includes("hick") || s.includes("miller") || s.includes("cognitive")) return "Cognitive";
  if (s.includes("material")) return "Material";
  return "Other";
}

function scoreInfo(score: number) {
  if (score >= 90) return { grade: "A", gradeColor: "text-emerald-400", ringColor: "#34d399" };
  if (score >= 75) return { grade: "B", gradeColor: "text-green-400",   ringColor: "#4ade80" };
  if (score >= 60) return { grade: "C", gradeColor: "text-yellow-400",  ringColor: "#facc15" };
  if (score >= 40) return { grade: "D", gradeColor: "text-orange-400",  ringColor: "#fb923c" };
  return             { grade: "F", gradeColor: "text-red-400",     ringColor: "#f87171" };
}

function computeScore(c: number, h: number, m: number, l: number) {
  return Math.max(0, 100 - (c * 15 + h * 7 + m * 3 + l));
}

function getIssueStatus(key: string) {
  try {
    const v = localStorage.getItem(key);
    if (v === "fixed" || v === "in_progress" || v === "wont_fix") return v;
  } catch {}
  return "open";
}

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const d = Math.floor(hrs / 24);
  if (d === 1) return "yesterday";
  if (d < 7) return `${d}d ago`;
  return new Date(iso).toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

// ── Compute ───────────────────────────────────────────────────────────────────

function compute(): DashboardData {
  const sessions = loadSessions();
  const allIssues: RawIssue[] = [];
  const sessionStats: SessionStat[] = [];
  const topOpenIssues: OpenIssue[] = [];
  let critiqueSessions = 0;

  for (const session of sessions) {
    const messages = loadMessages(session.id);
    const sessionIssues: RawIssue[] = [];

    for (const msg of messages) {
      if (!msg.critiqueData) continue;
      const d = msg.critiqueData;
      const combined: RawIssue[] = [
        ...(Array.isArray(d.issues) ? d.issues : []),
        ...(Array.isArray(d.flow_issues) ? d.flow_issues : []),
        ...(Array.isArray(d.trust_safety) ? d.trust_safety : []),
        ...(Array.isArray(d.localization_inclusivity) ? d.localization_inclusivity : []),
      ];
      sessionIssues.push(...combined);
      allIssues.push(...combined);
    }

    if (sessionIssues.length === 0) continue;
    critiqueSessions++;

    const sorted = [...sessionIssues].sort(
      (a, b) => (SEV_ORDER[a.severity?.toLowerCase()] ?? 3) - (SEV_ORDER[b.severity?.toLowerCase()] ?? 3)
    );
    const sev = { critical: 0, high: 0, medium: 0, low: 0 };
    sorted.forEach((issue, i) => {
      const s = (issue.severity?.toLowerCase() ?? "low") as keyof typeof sev;
      if (s in sev) sev[s]++; else sev.low++;
      if ((s === "critical" || s === "high") && topOpenIssues.length < 5) {
        if (getIssueStatus(`don_issue_${session.id}_${i}`) === "open") {
          topOpenIssues.push({
            sessionId: session.id,
            sessionTitle: session.title || "Untitled",
            element: (issue as { element?: string }).element || "Element",
            description: (issue as { description?: string }).description || "",
            severity: s,
            citation: issue.rule_citation || "",
          });
        }
      }
    });

    const score = computeScore(sev.critical, sev.high, sev.medium, sev.low);
    const info = scoreInfo(score);
    sessionStats.push({
      id: session.id, title: session.title || "Untitled session",
      updatedAt: session.updatedAt, score, ...info,
      issueCount: sorted.length, criticalCount: sev.critical, highCount: sev.high,
    });
  }

  const bySeverity = { critical: 0, high: 0, medium: 0, low: 0 };
  for (const issue of allIssues) {
    const s = (issue.severity?.toLowerCase() ?? "low") as keyof typeof bySeverity;
    if (s in bySeverity) bySeverity[s]++; else bySeverity.low++;
  }

  const catMap: Record<string, number> = {};
  for (const issue of allIssues) {
    const cat = categorize(issue.rule_citation || "");
    catMap[cat] = (catMap[cat] ?? 0) + 1;
  }
  const byCategory = Object.entries(catMap)
    .sort((a, b) => b[1] - a[1])
    .map(([name, count]) => ({ name, count, ...(CAT_CFG[name] ?? CAT_CFG.Other) }));

  const statusCounts = { open: 0, fixed: 0, in_progress: 0, wont_fix: 0 };
  let nonOpen = 0;
  try {
    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i);
      if (!key?.startsWith("don_issue_")) continue;
      const status = localStorage.getItem(key) as keyof typeof statusCounts | null;
      if (status && status !== "open" && status in statusCounts) { statusCounts[status]++; nonOpen++; }
    }
  } catch {}
  statusCounts.open = Math.max(0, allIssues.length - nonOpen);

  const fixRate = allIssues.length > 0
    ? Math.round(((statusCounts.fixed + statusCounts.wont_fix) / allIssues.length) * 100)
    : 0;

  const avgScore = sessionStats.length > 0
    ? Math.round(sessionStats.reduce((s, ss) => s + ss.score, 0) / sessionStats.length)
    : 100;

  let trend: "up" | "down" | "flat" = "flat";
  if (sessionStats.length >= 2) {
    const mid = Math.floor(sessionStats.length / 2);
    const avgOlder = sessionStats.slice(mid).reduce((s, ss) => s + ss.score, 0) / (sessionStats.length - mid);
    const avgNewer = sessionStats.slice(0, mid).reduce((s, ss) => s + ss.score, 0) / mid;
    if (avgNewer > avgOlder + 5) trend = "up";
    else if (avgNewer < avgOlder - 5) trend = "down";
  }

  const info = scoreInfo(avgScore);
  return {
    healthScore: avgScore, ...info,
    totalSessions: sessions.length, critiqueSessions,
    totalIssues: allIssues.length,
    openUrgent: Math.max(0, (bySeverity.critical || 0) + (bySeverity.high || 0) - (statusCounts.fixed || 0)),
    fixRate, trend,
    bySeverity, byStatus: statusCounts, byCategory,
    sessionStats, topOpenIssues,
  };
}

// ── SVG Sparkline ─────────────────────────────────────────────────────────────

function Sparkline({ sessions }: { sessions: SessionStat[] }) {
  if (sessions.length < 2) return (
    <p className="text-xs text-zinc-600 py-8 text-center">Run more critiques to see the trend</p>
  );

  const pts = [...sessions].reverse();
  const W = 560, H = 96;
  const pad = { t: 10, r: 6, b: 20, l: 24 };
  const iW = W - pad.l - pad.r, iH = H - pad.t - pad.b;
  const max = Math.max(...pts.map(s => s.issueCount), 1);

  const coords = pts.map((s, i) => ({
    x: pad.l + (i / Math.max(pts.length - 1, 1)) * iW,
    y: pad.t + iH - (s.issueCount / max) * iH,
    s,
  }));

  let line = `M ${coords[0].x} ${coords[0].y}`;
  for (let i = 1; i < coords.length; i++) {
    const cx = (coords[i - 1].x + coords[i].x) / 2;
    line += ` C ${cx} ${coords[i-1].y} ${cx} ${coords[i].y} ${coords[i].x} ${coords[i].y}`;
  }
  const area = line + ` L ${coords[coords.length-1].x} ${pad.t + iH} L ${coords[0].x} ${pad.t + iH} Z`;

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full" preserveAspectRatio="none">
      <defs>
        <linearGradient id="sg" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%"   stopColor="#6366f1" stopOpacity="0.18" />
          <stop offset="100%" stopColor="#6366f1" stopOpacity="0" />
        </linearGradient>
      </defs>
      {[0, 0.5, 1].map(p => (
        <line key={p} x1={pad.l} y1={pad.t + iH * (1-p)} x2={pad.l + iW} y2={pad.t + iH * (1-p)}
          stroke="#27272a" strokeWidth="1" />
      ))}
      {[0, Math.round(max/2), max].map((v, i) => (
        <text key={i} x={pad.l - 4} y={pad.t + iH * (1 - v/max) + 3}
          textAnchor="end" fontSize="8" fill="#3f3f46">{v}</text>
      ))}
      <path d={area} fill="url(#sg)" />
      <path d={line} fill="none" stroke="#6366f1" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
      {coords.map(({ x, y, s }, i) => (
        <circle key={i} cx={x} cy={y} r="3" fill={s.ringColor} stroke="#09090b" strokeWidth="1.5" />
      ))}
      {pts.length <= 5 && coords.map(({ x, s }, i) => (
        <text key={i} x={x} y={H - 4} textAnchor="middle" fontSize="8" fill="#3f3f46">
          {s.title.length > 8 ? s.title.slice(0, 7) + "…" : s.title}
        </text>
      ))}
    </svg>
  );
}

// ── Bar row ───────────────────────────────────────────────────────────────────

function BarRow({ label, count, total, barColor, labelColor }: {
  label: string; count: number; total: number; barColor: string; labelColor: string;
}) {
  const pct = total > 0 ? (count / total) * 100 : 0;
  return (
    <div className="flex items-center gap-3">
      <span className={`text-[12px] font-medium w-[72px] shrink-0 ${count > 0 ? labelColor : "text-zinc-600"}`}>{label}</span>
      <div className="flex-1 bg-white/[0.04] rounded-full h-[5px] overflow-hidden">
        <div className={`h-[5px] rounded-full ${count > 0 ? barColor : ""} transition-all duration-700`}
          style={{ width: `${Math.max(pct, count > 0 ? 3 : 0)}%` }} />
      </div>
      <span className="text-[11px] text-zinc-500 w-[50px] text-right shrink-0 tabular-nums">
        {count > 0 ? `${count} · ${Math.round(pct)}%` : <span className="text-zinc-700">—</span>}
      </span>
    </div>
  );
}

// ── Severity badge ────────────────────────────────────────────────────────────

function SevBadge({ sev }: { sev: string }) {
  const styles: Record<string, string> = {
    critical: "bg-red-950/60 text-red-400 border-red-800/40",
    high:     "bg-orange-950/60 text-orange-400 border-orange-800/40",
    medium:   "bg-yellow-950/60 text-yellow-400 border-yellow-800/40",
    low:      "bg-zinc-900 text-zinc-500 border-zinc-700/50",
  };
  return (
    <span className={`inline-flex items-center rounded-md border px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider ${styles[sev] ?? styles.low}`}>
      {sev}
    </span>
  );
}

// ── Grade chip ────────────────────────────────────────────────────────────────

function GradeChip({ grade }: { grade: string }) {
  const styles: Record<string, string> = {
    A: "bg-emerald-950/60 text-emerald-400 border-emerald-800/40",
    B: "bg-green-950/60 text-green-400 border-green-800/40",
    C: "bg-yellow-950/60 text-yellow-400 border-yellow-800/40",
    D: "bg-orange-950/60 text-orange-400 border-orange-800/40",
    F: "bg-red-950/60 text-red-400 border-red-800/40",
  };
  return (
    <span className={`inline-flex w-8 h-8 items-center justify-center rounded-lg border text-xs font-bold shrink-0 ${styles[grade] ?? styles.F}`}>
      {grade}
    </span>
  );
}

// ── Score ring ────────────────────────────────────────────────────────────────

function ScoreRing({ score, grade, gradeColor, ringColor }: {
  score: number; grade: string; gradeColor: string; ringColor: string;
}) {
  const R = 30, circ = 2 * Math.PI * R;
  return (
    <div className="relative flex items-center justify-center w-[72px] h-[72px] shrink-0">
      <svg width="72" height="72" viewBox="0 0 72 72" className="-rotate-90">
        <circle cx="36" cy="36" r={R} fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth="6" />
        <circle cx="36" cy="36" r={R} fill="none" stroke={ringColor} strokeWidth="6"
          strokeDasharray={`${(score / 100) * circ} ${circ}`} strokeLinecap="round"
          style={{ transition: "stroke-dasharray 1s ease" }} />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center gap-0">
        <span className={`text-xl font-bold leading-none ${gradeColor}`}>{grade}</span>
        <span className="text-[9px] text-zinc-600 font-medium mt-0.5">{score}</span>
      </div>
    </div>
  );
}

// ── Section header ────────────────────────────────────────────────────────────

function SectionHeader({ icon: Icon, title, right }: {
  icon: React.ElementType; title: string; right?: React.ReactNode;
}) {
  return (
    <div className="flex items-center justify-between mb-4">
      <div className="flex items-center gap-2">
        <Icon className="h-3.5 w-3.5 text-zinc-600" />
        <span className="text-[11px] font-semibold uppercase tracking-wider text-zinc-500">{title}</span>
      </div>
      {right}
    </div>
  );
}

// ── Main ──────────────────────────────────────────────────────────────────────

export default function DashboardPage() {
  const router = useRouter();
  const [data, setData] = useState<DashboardData | null>(null);
  const [evalScores, setEvalScores] = useState<EvalScores | null>(null);

  useEffect(() => {
    setData(compute());
    getEvalScores()
      .then(setEvalScores)
      .catch(() => { /* eval scores are optional — never block the dashboard */ });
  }, []);

  if (data === null) {
    return (
      <div className="flex flex-col h-full bg-zinc-950 overflow-y-auto">
        <div className="border-b border-white/[0.06] px-6 h-[56px] flex items-center shrink-0">
          <div className="flex items-center gap-2"><BarChart2 className="h-4 w-4 text-zinc-500" /><span className="text-sm font-medium text-zinc-400">Activity</span></div>
        </div>
        <div className="p-6 space-y-3">
          {[...Array(4)].map((_, i) => <div key={i} className="h-20 rounded-xl bg-white/[0.02] animate-pulse border border-white/[0.04]" />)}
        </div>
      </div>
    );
  }

  const isEmpty = data.critiqueSessions === 0;

  return (
    <div className="flex flex-col h-full bg-zinc-950 overflow-y-auto">

      {/* ── Header (matches all other pages) ── */}
      <div className="border-b border-white/[0.06] px-6 h-[56px] flex items-center justify-between shrink-0">
        <div className="flex items-center gap-2">
          <BarChart2 className="h-4 w-4 text-zinc-500" />
          <p className="text-sm font-medium text-zinc-400">Activity</p>
        </div>
        {!isEmpty && (
          <button onClick={() => router.push("/")}
            className="text-xs text-zinc-500 hover:text-zinc-300 transition-colors">
            New critique →
          </button>
        )}
      </div>

      <div className="flex-1 px-6 py-6 max-w-4xl w-full mx-auto">

        {/* ── Page title (matches Playbooks / Evidence) ── */}
        <div className="mb-6">
          <h1 className="text-base font-semibold text-zinc-100">Design quality at a glance</h1>
          <p className="mt-1 text-sm text-zinc-500 leading-relaxed">
            Aggregate UX health metrics from all critique sessions.
          </p>
        </div>

        {/* ── Empty state ── */}
        {isEmpty && (
          <div className="flex flex-col items-center justify-center py-24 gap-5 text-center">
            <div className="h-12 w-12 rounded-xl border border-white/[0.06] bg-white/[0.02] flex items-center justify-center">
              <BarChart2 className="h-5 w-5 text-zinc-700" />
            </div>
            <div>
              <p className="text-sm font-medium text-zinc-300">No critique data yet</p>
              <p className="text-xs text-zinc-600 mt-1.5 max-w-xs leading-relaxed">
                Run your first design critique to start tracking UX quality scores and issue patterns.
              </p>
            </div>
            <button onClick={() => router.push("/")}
              className="inline-flex items-center gap-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 px-4 py-2 text-sm font-medium text-white transition-colors">
              Start a critique <ArrowRight className="h-3.5 w-3.5" />
            </button>
          </div>
        )}

        {!isEmpty && (
          <div className="space-y-4">

            {/* ══ Impact overview — single unified card ══ */}
            <div className="rounded-xl border border-white/[0.07] bg-white/[0.02] p-5">
              <div className="flex items-start justify-between gap-4 mb-5">
                <p className="text-sm font-medium text-zinc-300">Impact overview</p>
                {/* Trend pill */}
                <span className={`inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-[11px] font-medium ${
                  data.trend === "up"   ? "bg-emerald-950/60 text-emerald-400 border-emerald-800/40" :
                  data.trend === "down" ? "bg-red-950/60 text-red-400 border-red-800/40" :
                                          "bg-zinc-900 text-zinc-500 border-zinc-700/50"
                }`}>
                  {data.trend === "up"   && <TrendingUp   className="h-3 w-3" />}
                  {data.trend === "down" && <TrendingDown className="h-3 w-3" />}
                  {data.trend === "flat" && <Minus        className="h-3 w-3" />}
                  {data.trend === "up" ? "Improving" : data.trend === "down" ? "Declining" : "Stable"}
                </span>
              </div>

              {/* 3-column metrics */}
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-px bg-white/[0.04] rounded-lg overflow-hidden">

                {/* UX Health */}
                <div className="bg-zinc-950 px-5 py-4 flex items-center gap-4">
                  <ScoreRing
                    score={data.healthScore} grade={data.grade}
                    gradeColor={data.gradeColor} ringColor={data.ringColor}
                  />
                  <div>
                    <p className="text-[11px] text-zinc-500 font-medium uppercase tracking-wider">UX Health</p>
                    <p className={`text-2xl font-bold leading-tight mt-0.5 ${data.gradeColor}`}>{data.healthScore}<span className="text-sm font-normal text-zinc-600">/100</span></p>
                    <p className="text-[11px] text-zinc-600 mt-0.5">
                      avg across {data.critiqueSessions} critique{data.critiqueSessions !== 1 ? "s" : ""}
                    </p>
                  </div>
                </div>

                {/* Critiques */}
                <button className="bg-zinc-950 px-5 py-4 text-left hover:bg-white/[0.02] transition-colors"
                  onClick={() => router.push("/history")}>
                  <p className="text-[11px] text-zinc-500 font-medium uppercase tracking-wider">Critiques Run</p>
                  <p className="text-2xl font-bold text-zinc-100 leading-tight mt-0.5">
                    {data.critiqueSessions}
                    <span className="text-sm font-normal text-zinc-600"> / {data.totalSessions}</span>
                  </p>
                  <p className="text-[11px] text-zinc-600 mt-0.5">{data.totalIssues} issues found total</p>
                </button>

                {/* Open urgent */}
                <button className="bg-zinc-950 px-5 py-4 text-left hover:bg-white/[0.02] transition-colors"
                  onClick={() => router.push("/history")}>
                  <p className="text-[11px] text-zinc-500 font-medium uppercase tracking-wider">Open Urgent</p>
                  <p className={`text-2xl font-bold leading-tight mt-0.5 ${data.openUrgent > 0 ? "text-red-400" : "text-emerald-400"}`}>
                    {Math.max(0, data.openUrgent)}
                  </p>
                  <p className="text-[11px] text-zinc-600 mt-0.5">
                    {data.bySeverity.critical > 0
                      ? `${data.bySeverity.critical} critical · ${data.bySeverity.high} high`
                      : "no critical or high issues"}
                  </p>
                </button>
              </div>

              {/* Resolution progress strip */}
              {data.totalIssues > 0 && (
                <div className="mt-4 flex items-center gap-3">
                  <span className="text-[11px] text-zinc-600 w-24 shrink-0">
                    {data.fixRate > 0 ? `${data.fixRate}% resolved` : "Resolution"}
                  </span>
                  <div className="flex-1 bg-white/[0.04] rounded-full h-1.5 overflow-hidden">
                    <div className="h-1.5 rounded-full bg-emerald-500 transition-all duration-700"
                      style={{ width: `${data.fixRate}%` }} />
                  </div>
                  <span className="text-[11px] text-zinc-600 w-28 text-right shrink-0">
                    {data.byStatus.fixed} fixed · {data.byStatus.open} open
                  </span>
                </div>
              )}
            </div>

            {/* ══ Auto-eval quality (only shown when at least one eval exists) ══ */}
            {evalScores && evalScores.count > 0 && (() => {
              const avgs = evalScores.averages;
              const dims: Array<{ key: string; label: string; color: string }> = [
                { key: "fix_specificity",      label: "Fix specificity",      color: "bg-indigo-500" },
                { key: "severity_calibration", label: "Severity calibration", color: "bg-violet-500" },
                { key: "insight_depth",        label: "Insight depth",        color: "bg-sky-500" },
                { key: "rule_grounding",       label: "Rule grounding",       color: "bg-emerald-500" },
              ];
              const overall = avgs.overall ?? 0;
              const overallPct = Math.round(overall * 100);
              return (
                <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-5">
                  <div className="flex items-center justify-between mb-4">
                    <div className="flex items-center gap-2">
                      <Sparkles className="h-3.5 w-3.5 text-zinc-600" />
                      <span className="text-[11px] font-semibold uppercase tracking-wider text-zinc-500">
                        Critique quality
                      </span>
                    </div>
                    <span className="text-[11px] text-zinc-600">
                      avg across {evalScores.count} critique{evalScores.count !== 1 ? "s" : ""}
                    </span>
                  </div>
                  <div className="flex items-center gap-4 mb-4">
                    <p className={`text-3xl font-bold tabular-nums leading-none ${
                      overallPct >= 75 ? "text-emerald-400" :
                      overallPct >= 50 ? "text-yellow-400" : "text-red-400"
                    }`}>
                      {overallPct}<span className="text-sm font-normal text-zinc-600">%</span>
                    </p>
                    <p className="text-xs text-zinc-500 leading-relaxed">
                      Overall score from Gemini auto-eval — measures fix specificity,<br />
                      severity calibration, insight depth, and rule grounding.
                    </p>
                  </div>
                  <div className="space-y-2.5">
                    {dims.map(({ key, label, color }) => {
                      const val = avgs[key] ?? 0;
                      const pct = Math.round(val * 100);
                      return (
                        <div key={key} className="flex items-center gap-3">
                          <span className="text-[12px] text-zinc-500 w-[148px] shrink-0">{label}</span>
                          <div className="flex-1 bg-white/[0.04] rounded-full h-[5px] overflow-hidden">
                            <div className={`h-[5px] rounded-full ${color} transition-all duration-700`}
                              style={{ width: `${Math.max(pct, pct > 0 ? 3 : 0)}%` }} />
                          </div>
                          <span className="text-[11px] text-zinc-500 w-8 text-right tabular-nums">{pct}%</span>
                        </div>
                      );
                    })}
                  </div>
                </div>
              );
            })()}

            {/* ══ Issue trend ══ */}
            {data.sessionStats.length >= 2 && (
              <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] px-5 py-4">
                <SectionHeader icon={Activity} title="Issue trend"
                  right={
                    <div className="flex items-center gap-3 text-[11px] text-zinc-600">
                      <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-emerald-400 inline-block" />Good</span>
                      <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-yellow-400 inline-block" />Fair</span>
                      <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-red-400 inline-block" />Poor</span>
                    </div>
                  }
                />
                <Sparkline sessions={data.sessionStats.slice(0, 10)} />
              </div>
            )}

            {/* ══ Breakdown: Severity + Categories ══ */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-5">
                <SectionHeader icon={AlertTriangle} title="Severity breakdown" />
                <div className="space-y-3">
                  <BarRow label="Critical" count={data.bySeverity.critical} total={data.totalIssues} barColor="bg-red-500"    labelColor="text-red-400" />
                  <BarRow label="High"     count={data.bySeverity.high}     total={data.totalIssues} barColor="bg-orange-500" labelColor="text-orange-400" />
                  <BarRow label="Medium"   count={data.bySeverity.medium}   total={data.totalIssues} barColor="bg-yellow-500" labelColor="text-yellow-400" />
                  <BarRow label="Low"      count={data.bySeverity.low}      total={data.totalIssues} barColor="bg-zinc-500"   labelColor="text-zinc-400" />
                </div>
              </div>

              <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-5">
                <SectionHeader icon={Layers} title="Violation categories" />
                {data.byCategory.length > 0 ? (
                  <div className="space-y-3">
                    {data.byCategory.slice(0, 5).map(({ name, count, bar, label }) => (
                      <BarRow key={name} label={name} count={count}
                        total={data.byCategory[0]?.count ?? 1} barColor={bar} labelColor={label} />
                    ))}
                  </div>
                ) : (
                  <p className="text-xs text-zinc-600">No category data yet</p>
                )}
              </div>
            </div>

            {/* ══ Needs attention ══ */}
            {data.topOpenIssues.length > 0 && (
              <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] overflow-hidden">
                <div className="flex items-center justify-between px-5 py-3.5 border-b border-white/[0.04]">
                  <div className="flex items-center gap-2">
                    <Flame className="h-3.5 w-3.5 text-orange-400" />
                    <span className="text-[11px] font-semibold uppercase tracking-wider text-zinc-400">Needs attention</span>
                  </div>
                  <span className="text-[11px] text-zinc-600">{data.topOpenIssues.length} open</span>
                </div>
                <div className="divide-y divide-white/[0.04]">
                  {data.topOpenIssues.slice(0, 4).map((issue, i) => (
                    <button key={i} onClick={() => router.push(`/?s=${issue.sessionId}`)}
                      className="w-full flex items-start gap-3 px-5 py-3.5 hover:bg-white/[0.02] transition-colors group text-left">
                      <SevBadge sev={issue.severity} />
                      <div className="flex-1 min-w-0">
                        <p className="text-sm text-zinc-300 font-medium truncate group-hover:text-zinc-100 transition-colors">
                          {issue.element}
                        </p>
                        {issue.description && (
                          <p className="text-xs text-zinc-600 mt-0.5 line-clamp-1">{issue.description}</p>
                        )}
                        {issue.citation && (
                          <p className="text-[10px] text-zinc-700 mt-1 font-mono">{issue.citation}</p>
                        )}
                      </div>
                      <div className="flex flex-col items-end gap-1 shrink-0">
                        <span className="text-[11px] text-zinc-600 max-w-[100px] truncate">{issue.sessionTitle}</span>
                        <ChevronRight className="h-3.5 w-3.5 text-zinc-700 group-hover:text-zinc-400 transition-colors" />
                      </div>
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* ══ All critiques table ══ */}
            {data.sessionStats.length > 0 && (
              <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] overflow-hidden">
                <div className="flex items-center justify-between px-5 py-3.5 border-b border-white/[0.04]">
                  <div className="flex items-center gap-2">
                    <Target className="h-3.5 w-3.5 text-zinc-600" />
                    <span className="text-[11px] font-semibold uppercase tracking-wider text-zinc-500">All critiques</span>
                  </div>
                  <span className="text-[11px] text-zinc-600">{data.sessionStats.length} sessions</span>
                </div>

                {/* Header */}
                <div className="hidden sm:grid grid-cols-[32px_1fr_60px_70px_80px_70px] gap-4 px-5 py-2 border-b border-white/[0.04]">
                  {["", "Session", "Issues", "Critical", "Score", ""].map((h, i) => (
                    <span key={i} className="text-[10px] font-semibold uppercase tracking-wider text-zinc-700">{h}</span>
                  ))}
                </div>

                <div className="divide-y divide-white/[0.04]">
                  {data.sessionStats.slice(0, 8).map((s) => (
                    <button key={s.id} onClick={() => router.push(`/?s=${s.id}`)}
                      className="w-full group text-left hover:bg-white/[0.02] transition-colors
                        flex items-center gap-3 px-5 py-3 sm:grid sm:grid-cols-[32px_1fr_60px_70px_80px_70px] sm:gap-4">
                      <GradeChip grade={s.grade} />
                      <p className="text-sm text-zinc-300 font-medium truncate group-hover:text-zinc-100 transition-colors">
                        {s.title}
                      </p>
                      <span className="hidden sm:block text-sm text-zinc-500 tabular-nums">{s.issueCount}</span>
                      <span className={`hidden sm:block text-sm tabular-nums font-medium ${s.criticalCount > 0 ? "text-red-400" : "text-zinc-700"}`}>
                        {s.criticalCount > 0 ? s.criticalCount : "—"}
                      </span>
                      {/* Mini score bar */}
                      <div className="hidden sm:flex items-center gap-2">
                        <div className="flex-1 bg-white/[0.04] rounded-full h-1.5 overflow-hidden">
                          <div className="h-1.5 rounded-full transition-all duration-500"
                            style={{ width: `${s.score}%`, backgroundColor: s.ringColor }} />
                        </div>
                      </div>
                      <div className="flex items-center justify-end gap-2 shrink-0 ml-auto sm:ml-0">
                        <span className="text-[11px] text-zinc-600">{timeAgo(s.updatedAt)}</span>
                        <ChevronRight className="h-3.5 w-3.5 text-zinc-700 group-hover:text-zinc-400 transition-colors" />
                      </div>
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* Resolution CTA */}
            {data.byStatus.fixed === 0 && data.totalIssues > 0 && (
              <p className="text-xs text-zinc-600 text-center py-2">
                Mark issues as fixed in your critique reports to track resolution progress.{" "}
                <button onClick={() => router.push("/")} className="text-indigo-500 hover:text-indigo-400 transition-colors">
                  Open latest critique →
                </button>
              </p>
            )}

          </div>
        )}
      </div>
    </div>
  );
}

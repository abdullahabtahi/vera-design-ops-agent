"use client";

import { useState } from "react";
import { Copy, Check, Download } from "lucide-react";
import { exportToFigmaComments, postIssueFeedback } from "../../lib/api";
import { storageKey } from "../lib/storage";

// ── Issue status tracker ───────────────────────────────────────────────────────

type IssueStatus = "open" | "fixed" | "in_progress" | "wont_fix";

const STATUS_CONFIG: Record<IssueStatus, { label: string; pill: string; dimmed: boolean }> = {
  open:        { label: "Open",        pill: "",                                                          dimmed: false },
  fixed:       { label: "Fixed",       pill: "bg-emerald-900/60 text-emerald-300 border-emerald-700/50", dimmed: true  },
  in_progress: { label: "In Progress", pill: "bg-amber-900/60 text-amber-300 border-amber-700/50",       dimmed: false },
  wont_fix:    { label: "Won't Fix",   pill: "bg-zinc-800/80 text-zinc-500 border-zinc-700/50",          dimmed: true  },
};

function loadIssueStatus(key: string): IssueStatus {
  try { return (localStorage.getItem(key) as IssueStatus) ?? "open"; } catch { return "open"; }
}

function saveIssueStatus(key: string, status: IssueStatus) {
  try {
    if (status === "open") localStorage.removeItem(key);
    else localStorage.setItem(key, status);
  } catch {}
}

// ── Severity ──────────────────────────────────────────────────────────────────

const SEV = {
  critical: { label: "Critical", bg: "bg-red-950/60",    border: "border-red-800",    badge: "bg-red-700 text-red-100" },
  high:     { label: "High",     bg: "bg-orange-950/60", border: "border-orange-800", badge: "bg-orange-700 text-orange-100" },
  medium:   { label: "Medium",   bg: "bg-yellow-950/60", border: "border-yellow-800", badge: "bg-yellow-700 text-yellow-100" },
  low:      { label: "Low",      bg: "bg-zinc-900/60",   border: "border-zinc-700",   badge: "bg-zinc-700 text-zinc-200" },
} as const;
type Severity = keyof typeof SEV;

// ── Context alignment ─────────────────────────────────────────────────────────

const ALIGNMENT = {
  strong:     { label: "Strong fit",  bg: "bg-emerald-950/50", border: "border-emerald-800", text: "text-emerald-400" },
  partial:    { label: "Partial fit", bg: "bg-yellow-950/50",  border: "border-yellow-800",  text: "text-yellow-400" },
  misaligned: { label: "Misaligned",  bg: "bg-red-950/50",     border: "border-red-800",      text: "text-red-400" },
};

// ── Types ─────────────────────────────────────────────────────────────────────

/* eslint-disable @typescript-eslint/no-explicit-any */
type Report = Record<string, any>;

// ── Copy fix button ───────────────────────────────────────────────────────────

function CopyFixButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  function handleCopy() {
    navigator.clipboard.writeText(text).catch(() => {});
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }
  return (
    <button
      onClick={handleCopy}
      title="Copy fix"
      className="shrink-0 flex items-center gap-1 px-1.5 py-0.5 rounded text-[11px] text-zinc-600 hover:text-zinc-300 hover:bg-white/[0.05] transition-colors"
    >
      {copied ? <Check className="h-2.5 w-2.5 text-emerald-400" /> : <Copy className="h-2.5 w-2.5" />}
      {copied ? "Copied" : "Copy fix"}
    </button>
  );
}

// ── Sub-components ────────────────────────────────────────────────────────────

const STATUS_ACTIONS: { status: IssueStatus; label: string; active: string; inactive: string }[] = [
  { status: "fixed",       label: "✓ Fixed",       active: "bg-emerald-800/80 text-emerald-200 border-emerald-700", inactive: "text-zinc-600 border-white/[0.06] hover:text-emerald-400 hover:border-emerald-700/40" },
  { status: "in_progress", label: "⟳ Working",     active: "bg-amber-800/80 text-amber-200 border-amber-700",      inactive: "text-zinc-600 border-white/[0.06] hover:text-amber-400 hover:border-amber-700/40" },
  { status: "wont_fix",    label: "— Won't Fix",   active: "bg-zinc-700 text-zinc-300 border-zinc-600",            inactive: "text-zinc-600 border-white/[0.06] hover:text-zinc-400 hover:border-zinc-600/40" },
];

function IssueCard({
  item,
  issueKey,
  sessionId,
  issueIndex,
}: {
  item: Record<string, any>;
  issueKey?: string;
  sessionId?: string;
  issueIndex?: number;
}) {
  const sev = (item.severity as Severity) in SEV ? (item.severity as Severity) : "low";
  const cfg = SEV[sev];

  const mountedAtRef = useState<number>(() => Date.now())[0];

  const [status, setStatus] = useState<IssueStatus>(() =>
    issueKey ? loadIssueStatus(issueKey) : "open"
  );

  function handleStatus(next: IssueStatus) {
    const newStatus = status === next ? "open" : next;
    setStatus(newStatus);
    if (issueKey) saveIssueStatus(issueKey, newStatus);

    // Fire-and-forget feedback to backend
    if (sessionId && issueIndex !== undefined) {
      postIssueFeedback({
        session_id: sessionId,
        issue_index: issueIndex,
        element: item.element ?? "",
        severity: item.severity ?? "",
        rule_citation: item.rule_citation ?? "",
        status: newStatus,
        time_to_action_ms: Date.now() - mountedAtRef,
      });
    }
  }

  const isDimmed = STATUS_CONFIG[status].dimmed;

  return (
    <div className={`rounded-lg border p-3 transition-opacity ${cfg.bg} ${cfg.border} ${isDimmed ? "opacity-50" : ""}`}>
      <div className="flex items-start justify-between gap-2 mb-2">
        <span className="text-sm font-medium text-zinc-200">{item.element}</span>
        <div className="flex items-center gap-1.5 shrink-0">
          {status !== "open" && (
            <span className={`rounded border px-1.5 py-0.5 text-[11px] font-medium ${STATUS_CONFIG[status].pill}`}>
              {STATUS_CONFIG[status].label}
            </span>
          )}
          <span className={`shrink-0 rounded px-1.5 py-0.5 text-xs font-semibold ${cfg.badge}`}>
            {cfg.label}
          </span>
        </div>
      </div>
      <p className="text-xs text-zinc-300 mb-2">{item.issue}</p>
      <div className="rounded bg-black/30 px-2 py-1.5 mb-2">
        <div className="flex items-start justify-between gap-2">
          <p className="text-xs font-medium text-emerald-400">Fix</p>
          <CopyFixButton text={item.fix} />
        </div>
        <p className="text-xs text-zinc-300 mt-0.5">{item.fix}</p>
      </div>
      <p className="text-xs text-zinc-500">
        <span className="text-zinc-600">Rule: </span>{item.rule_citation}
        {item.wcag_sc && <span className="ml-2 text-blue-500">WCAG {item.wcag_sc}</span>}
      </p>
      {item.linked_persona && item.why_it_matters && (
        <p className="mt-1.5 text-xs text-indigo-400/80">
          <span className="text-zinc-600">↳ {item.linked_persona}: </span>{item.why_it_matters}
        </p>
      )}
      {/* Status tracker */}
      <div className="flex items-center gap-1.5 mt-2.5 pt-2 border-t border-white/[0.05]">
        <span className="text-[11px] text-zinc-700 mr-0.5">Mark:</span>
        {STATUS_ACTIONS.map(({ status: s, label, active, inactive }) => (
          <button
            key={s}
            onClick={() => handleStatus(s)}
            aria-label={`Mark as ${STATUS_CONFIG[s].label}`}
            className={`rounded border px-1.5 py-0.5 text-[11px] transition-colors ${status === s ? active : inactive}`}
          >
            {label}
          </button>
        ))}
      </div>
    </div>
  );
}

function SimpleCard({ item, categoryLabel }: { item: Record<string, any>; categoryLabel?: string }) {
  return (
    <div className="rounded-lg border border-zinc-800 bg-zinc-900/60 p-3">
      <div className="flex items-start justify-between gap-2 mb-1.5">
        <span className="text-sm font-medium text-zinc-200">{item.element}</span>
        {categoryLabel && (
          <span className="shrink-0 rounded px-1.5 py-0.5 text-xs bg-zinc-700 text-zinc-300">
            {categoryLabel}
          </span>
        )}
      </div>
      <p className="text-xs text-zinc-300 mb-2">{item.issue}</p>
      <div className="rounded bg-black/30 px-2 py-1.5">
        <div className="flex items-start justify-between gap-2">
          <p className="text-xs font-medium text-emerald-400">Fix</p>
          <CopyFixButton text={item.fix} />
        </div>
        <p className="text-xs text-zinc-300 mt-0.5">{item.fix}</p>
      </div>
    </div>
  );
}

// ── Markdown export ───────────────────────────────────────────────────────────

function formatAsMarkdown(report: Report): string {
  const lines: string[] = ["# Design Critique Report", ""];

  const dirSummary: string[] = Array.isArray(report.director_summary) ? report.director_summary : [];
  if (dirSummary.length) {
    lines.push("## Director's Take", "");
    for (const bullet of dirSummary) lines.push(`→ ${bullet}`);
    lines.push("");
  }

  lines.push(`## Frame\n${report.frame_description}`, "");
  lines.push(`## Overall Assessment\n${report.overall_assessment}`, "");

  if (report.context_alignment_score) {
    const score = String(report.context_alignment_score).toUpperCase();
    lines.push(`## Context Fit: ${score}`);
    if (report.context_alignment_notes) lines.push(report.context_alignment_notes);
    lines.push("");
  }

  const issues: any[] = Array.isArray(report.issues) ? report.issues : [];
  if (issues.length) {
    lines.push("## Issues", "");
    for (const item of issues) {
      const sev = String(item.severity ?? "low").toUpperCase();
      lines.push(`### [${sev}] ${item.element}`);
      lines.push(item.issue, "");
      lines.push(`**Fix:** ${item.fix}`, "");
      lines.push(`_Rule: ${item.rule_citation}${item.wcag_sc ? ` · WCAG ${item.wcag_sc}` : ""}_`);
      if (item.linked_persona && item.why_it_matters) {
        lines.push(`↳ **${item.linked_persona}:** ${item.why_it_matters}`);
      }
      lines.push("");
    }
  }

  const flowIssues: any[] = Array.isArray(report.flow_issues) ? report.flow_issues : [];
  if (flowIssues.length) {
    lines.push("## Flow & Navigation", "");
    for (const item of flowIssues) {
      lines.push(`- **${item.element}:** ${item.issue}`);
      lines.push(`  → Fix: ${item.fix}`);
    }
    lines.push("");
  }

  const trustSafety: any[] = Array.isArray(report.trust_safety) ? report.trust_safety : [];
  if (trustSafety.length) {
    lines.push("## Trust & Safety", "");
    for (const item of trustSafety) {
      const cat = (item.category ?? "").replace(/_/g, " ").toUpperCase();
      lines.push(`- **[${cat}] ${item.element}:** ${item.issue}`);
      lines.push(`  → Fix: ${item.fix}`);
    }
    lines.push("");
  }

  const localization: any[] = Array.isArray(report.localization_inclusivity) ? report.localization_inclusivity : [];
  if (localization.length) {
    lines.push("## Localization & Inclusivity", "");
    for (const item of localization) {
      const type = (item.type ?? "").replace(/_/g, " ").toUpperCase();
      lines.push(`- **[${type}] ${item.element}:** ${item.issue}`);
      lines.push(`  → Fix: ${item.fix}`);
    }
    lines.push("");
  }

  const positives: string[] = Array.isArray(report.positive_observations) ? report.positive_observations : [];
  if (positives.length) {
    lines.push("## What Works", "");
    for (const obs of positives) lines.push(`- ✓ ${obs}`);
    lines.push("");
  }

  const designNotes: string[] = Array.isArray(report.design_system_notes) ? report.design_system_notes : [];
  if (designNotes.length) {
    lines.push("## Design System Notes", "");
    for (const note of designNotes) lines.push(`- ${note}`);
    lines.push("");
  }

  const exps: string[] = Array.isArray(report.recommended_experiments) ? report.recommended_experiments : [];
  if (exps.length) {
    lines.push("## What to Test Next", "");
    exps.forEach((exp, i) => lines.push(`${i + 1}. ${exp}`));
    lines.push("");
  }

  lines.push("---", "*Generated by Design Ops Navigator*");
  return lines.join("\n");
}

// ── Export toolbar ────────────────────────────────────────────────────────────

type FigmaExportStatus = "idle" | "loading" | "success" | "error";

function ExportToolbar({
  report,
  figmaUrl,
  sessionId,
}: {
  report: Report;
  figmaUrl?: string;
  sessionId?: string;
}) {
  const [copied, setCopied] = useState(false);
  const [figmaStatus, setFigmaStatus] = useState<FigmaExportStatus>("idle");
  const [figmaMsg, setFigmaMsg] = useState("");

  function handleCopy() {
    const md = formatAsMarkdown(report);
    navigator.clipboard.writeText(md).catch(() => {});
    setCopied(true);
    setTimeout(() => setCopied(false), 2500);
  }

  function handleDownload() {
    const md = formatAsMarkdown(report);
    const blob = new Blob([md], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "design-critique.md";
    a.click();
    URL.revokeObjectURL(url);
  }

  async function handleExportFigma() {
    if (!figmaUrl || !sessionId || figmaStatus === "loading") return;
    setFigmaStatus("loading");
    setFigmaMsg("");
    try {
      const result = await exportToFigmaComments(
        sessionId,
        figmaUrl,
        report as Record<string, unknown>,
      );
      setFigmaStatus("success");
      setFigmaMsg(`${result.posted} comment${result.posted !== 1 ? "s" : ""} posted`);
      setTimeout(() => { setFigmaStatus("idle"); setFigmaMsg(""); }, 4000);
    } catch (err) {
      setFigmaStatus("error");
      setFigmaMsg(err instanceof Error ? err.message : "Export failed");
      setTimeout(() => { setFigmaStatus("idle"); setFigmaMsg(""); }, 4000);
    }
  }

  return (
    <div className="flex items-center gap-1.5 justify-end flex-wrap">
      {figmaUrl && sessionId && (
        <button
          onClick={handleExportFigma}
          disabled={figmaStatus === "loading"}
          title={figmaMsg || "Post critique as Figma comments"}
          className={`flex items-center gap-1.5 rounded-lg border px-2.5 py-1.5 text-xs transition-colors disabled:opacity-50 ${
            figmaStatus === "success"
              ? "border-emerald-700/60 bg-emerald-950/30 text-emerald-400"
              : figmaStatus === "error"
              ? "border-red-700/60 bg-red-950/30 text-red-400"
              : "border-white/[0.08] bg-white/[0.02] text-zinc-500 hover:text-zinc-300 hover:border-white/[0.16]"
          }`}
        >
          {figmaStatus === "loading" ? (
            <svg className="h-3 w-3 animate-spin" viewBox="0 0 24 24" fill="none">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
            </svg>
          ) : figmaStatus === "success" ? (
            <Check className="h-3 w-3" />
          ) : (
            <svg viewBox="0 0 38 57" fill="none" className="h-3 w-2.5 shrink-0">
              <path d="M19 28.5a9.5 9.5 0 1 1 19 0 9.5 9.5 0 0 1-19 0z" fill="currentColor" opacity="0.8" />
              <path d="M0 47.5A9.5 9.5 0 0 1 9.5 38H19v9.5a9.5 9.5 0 0 1-19 0z" fill="currentColor" opacity="0.6" />
              <path d="M19 0v19h9.5a9.5 9.5 0 0 0 0-19H19z" fill="currentColor" opacity="0.7" />
              <path d="M0 9.5A9.5 9.5 0 0 0 9.5 19H19V0H9.5A9.5 9.5 0 0 0 0 9.5z" fill="currentColor" opacity="0.5" />
              <path d="M0 28.5A9.5 9.5 0 0 0 9.5 38H19V19H9.5A9.5 9.5 0 0 0 0 28.5z" fill="currentColor" opacity="0.65" />
            </svg>
          )}
          {figmaStatus === "loading"
            ? "Posting…"
            : figmaStatus === "success"
            ? figmaMsg
            : figmaStatus === "error"
            ? "Failed"
            : "Export to Figma"}
        </button>
      )}
      <button
        onClick={handleCopy}
        className="flex items-center gap-1.5 rounded-lg border border-white/[0.08] bg-white/[0.02] px-2.5 py-1.5 text-xs text-zinc-500 hover:text-zinc-300 hover:border-white/[0.16] transition-colors"
      >
        {copied ? <Check className="h-3 w-3 text-emerald-400" /> : <Copy className="h-3 w-3" />}
        {copied ? "Copied!" : "Copy as Markdown"}
      </button>
      <button
        onClick={handleDownload}
        className="flex items-center gap-1.5 rounded-lg border border-white/[0.08] bg-white/[0.02] px-2.5 py-1.5 text-xs text-zinc-500 hover:text-zinc-300 hover:border-white/[0.16] transition-colors"
      >
        <Download className="h-3 w-3" />
        .md
      </button>
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

interface CritiqueReportProps {
  data?: Report;        // preferred: pre-parsed JSON from STATE_DELTA
  text?: string;        // fallback: parse from raw text
  figmaUrl?: string;    // Figma frame URL — enables "Export to Figma" button
  sessionId?: string;   // active session ID — required for the export endpoint
}

function parseFromText(text: string): Report | null {
  const match = text.match(/```json\n?([\s\S]*?)\n?```/) ?? text.match(/(\{[\s\S]*"issues"[\s\S]*\})/);
  const raw = match?.[1] ?? text;
  try { return JSON.parse(raw); } catch { return null; }
}

export function CritiqueReport({ data, text, figmaUrl, sessionId }: CritiqueReportProps) {
  const report: Report | null = data ?? (text ? parseFromText(text) : null);
  if (!report || !Array.isArray(report.issues)) return null;

  const orderedIssues = [...(report.issues as any[])].sort((a, b) => {
    const order: Severity[] = ["critical", "high", "medium", "low"];
    return order.indexOf(a.severity) - order.indexOf(b.severity);
  });

  const flowIssues: any[]          = Array.isArray(report.flow_issues) ? report.flow_issues : [];
  const trustSafety: any[]         = Array.isArray(report.trust_safety) ? report.trust_safety : [];
  const localization: any[]        = Array.isArray(report.localization_inclusivity) ? report.localization_inclusivity : [];
  const designNotes: string[]      = Array.isArray(report.design_system_notes) ? report.design_system_notes : [];
  const positives: string[]        = Array.isArray(report.positive_observations) ? report.positive_observations : [];
  const directorSummary: string[]  = Array.isArray(report.director_summary) ? report.director_summary : [];
  const experiments: string[]      = Array.isArray(report.recommended_experiments) ? report.recommended_experiments : [];

  const alignmentScore = report.context_alignment_score as keyof typeof ALIGNMENT | undefined;
  const alignmentCfg = alignmentScore ? ALIGNMENT[alignmentScore] : null;

  return (
    <div className="space-y-4">

      {/* Director's Take */}
      {directorSummary.length > 0 && (
        <div className="rounded-lg border border-violet-800/60 bg-violet-950/30 p-4">
          <p className="text-xs font-semibold uppercase tracking-wider text-violet-400 mb-2.5">Director's Take</p>
          <ul className="space-y-2">
            {directorSummary.map((bullet, i) => (
              <li key={i} className="flex gap-2.5 text-sm text-zinc-200">
                <span className="text-violet-400 shrink-0 mt-0.5">→</span>
                <span>{bullet}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Header */}
      <div className="rounded-lg border border-zinc-800 bg-zinc-900/60 p-4">
        <p className="text-xs font-semibold uppercase tracking-wider text-zinc-500 mb-1">Frame</p>
        <p className="text-sm text-zinc-300">{report.frame_description}</p>
        <p className="mt-2 text-sm text-zinc-400">{report.overall_assessment}</p>
      </div>

      {/* Context alignment */}
      {alignmentCfg && (
        <div className={`rounded-lg border px-3 py-2.5 ${alignmentCfg.bg} ${alignmentCfg.border}`}>
          <div className="flex items-center gap-2 mb-1">
            <p className="text-xs font-semibold uppercase tracking-wider text-zinc-500">Context Fit</p>
            <span className={`rounded px-1.5 py-0.5 text-xs font-semibold border ${alignmentCfg.text} ${alignmentCfg.border}`}>
              {alignmentCfg.label}
            </span>
          </div>
          {report.context_alignment_notes && (
            <p className="text-xs text-zinc-400">{report.context_alignment_notes}</p>
          )}
        </div>
      )}

      {/* Issue count summary + export toolbar */}
      <div className="flex items-center justify-between gap-2 flex-wrap">
        <div className="flex gap-2 flex-wrap">
          {(["critical", "high", "medium", "low"] as Severity[]).map(sev => {
            const count = orderedIssues.filter(i => i.severity === sev).length;
            if (!count) return null;
            return (
              <span key={sev} className={`rounded px-2 py-0.5 text-xs font-semibold ${SEV[sev].badge}`}>
                {count} {SEV[sev].label}
              </span>
            );
          })}
        </div>
        <ExportToolbar report={report} figmaUrl={figmaUrl} sessionId={sessionId} />
      </div>

      {/* Element-level Issues */}
      {orderedIssues.length > 0 && (
        <div className="space-y-2">
          <p className="text-xs font-semibold uppercase tracking-wider text-zinc-500">Issues</p>
          {orderedIssues.map((item, i) => (
            <IssueCard
              key={i}
              item={item}
              issueKey={sessionId ? storageKey(`issue.${sessionId}.${i}`) : undefined}
              sessionId={sessionId}
              issueIndex={i}
            />
          ))}
        </div>
      )}

      {/* Flow & Navigation */}
      {flowIssues.length > 0 && (
        <div className="space-y-2">
          <p className="text-xs font-semibold uppercase tracking-wider text-zinc-500">Flow & Navigation</p>
          {flowIssues.map((item, i) => <SimpleCard key={i} item={item} />)}
        </div>
      )}

      {/* Trust & Safety */}
      {trustSafety.length > 0 && (
        <div className="space-y-2">
          <p className="text-xs font-semibold uppercase tracking-wider text-zinc-500">Trust & Safety</p>
          {trustSafety.map((item, i) => (
            <SimpleCard key={i} item={item} categoryLabel={item.category?.replace(/_/g, " ")} />
          ))}
        </div>
      )}

      {/* Localization & Inclusivity */}
      {localization.length > 0 && (
        <div className="space-y-2">
          <p className="text-xs font-semibold uppercase tracking-wider text-zinc-500">Localization & Inclusivity</p>
          {localization.map((item, i) => (
            <SimpleCard key={i} item={item} categoryLabel={item.type?.replace(/_/g, " ")} />
          ))}
        </div>
      )}

      {/* What Works */}
      {positives.length > 0 && (
        <div className="rounded-lg border border-emerald-900 bg-emerald-950/30 p-3">
          <p className="text-xs font-semibold uppercase tracking-wider text-emerald-600 mb-2">What Works</p>
          <ul className="space-y-1">
            {positives.map((o, i) => (
              <li key={i} className="text-xs text-zinc-300 flex gap-2">
                <span className="text-emerald-500 shrink-0">✓</span>{o}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Design System */}
      {designNotes.length > 0 && (
        <div className="rounded-lg border border-zinc-800 bg-zinc-900/40 p-3">
          <p className="text-xs font-semibold uppercase tracking-wider text-zinc-500 mb-2">Design System</p>
          <ul className="space-y-1">
            {designNotes.map((n, i) => (
              <li key={i} className="text-xs text-zinc-400">• {n}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Recommended Experiments */}
      {experiments.length > 0 && (
        <div className="rounded-lg border border-sky-900/60 bg-sky-950/20 p-3">
          <p className="text-xs font-semibold uppercase tracking-wider text-sky-500 mb-2">What to Test Next</p>
          <ul className="space-y-2">
            {experiments.map((exp, i) => (
              <li key={i} className="flex gap-2 text-xs text-zinc-300">
                <span className="text-sky-500 shrink-0 font-semibold">{i + 1}.</span>
                <span>{exp}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

    </div>
  );
}

"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Clock, Figma, AlertTriangle, CheckCircle, ChevronRight, FileText } from "lucide-react";
import { loadSessions, loadMessages, SessionMeta, Message } from "../hooks/useAgentStream";

// ── Types ──────────────────────────────────────────────────────────────────────

interface IssueSummary {
  critical: number;
  high: number;
  medium: number;
  low: number;
  total: number;
}

interface SessionSummary extends SessionMeta {
  issueCount: IssueSummary | null;
  hasCritique: boolean;
}

// ── Helpers ────────────────────────────────────────────────────────────────────

function extractIssueSummary(messages: Message[]): IssueSummary | null {
  for (const msg of messages) {
    if (msg.critiqueData) {
      const data = msg.critiqueData;
      const issues: Array<{ severity?: string }> = data.issues ?? [];
      const flowIssues: Array<{ severity?: string }> = data.flow_issues ?? [];
      const trustIssues: Array<{ severity?: string }> = data.trust_safety ?? [];
      const all = [...issues, ...flowIssues, ...trustIssues];
      const count = { critical: 0, high: 0, medium: 0, low: 0, total: all.length };
      for (const issue of all) {
        const s = issue.severity?.toLowerCase() ?? "medium";
        if (s === "critical") count.critical++;
        else if (s === "high") count.high++;
        else if (s === "medium") count.medium++;
        else count.low++;
      }
      return count;
    }
  }
  return null;
}

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  if (days === 1) return "yesterday";
  if (days < 7) return `${days}d ago`;
  return new Date(iso).toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

function groupByDate(sessions: SessionSummary[]): Array<{ label: string; items: SessionSummary[] }> {
  const groups = new Map<string, SessionSummary[]>();
  for (const s of sessions) {
    const d = new Date(s.updatedAt);
    const today = new Date();
    const yesterday = new Date(today);
    yesterday.setDate(today.getDate() - 1);
    let label: string;
    if (d.toDateString() === today.toDateString()) label = "Today";
    else if (d.toDateString() === yesterday.toDateString()) label = "Yesterday";
    else label = d.toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric" });
    const arr = groups.get(label) ?? [];
    arr.push(s);
    groups.set(label, arr);
  }
  return Array.from(groups.entries()).map(([label, items]) => ({ label, items }));
}

// ── Row component ─────────────────────────────────────────────────────────────

function SessionRow({ session, onClick }: { session: SessionSummary; onClick: () => void }) {
  const { issueCount } = session;

  return (
    <button
      onClick={onClick}
      className="w-full flex items-start gap-4 rounded-xl border border-white/[0.06] bg-white/[0.02] px-4 py-3.5 text-left hover:bg-white/[0.04] hover:border-white/[0.1] transition-all group"
    >
      {/* Icon */}
      <div className="shrink-0 mt-0.5">
        {session.hasCritique ? (
          <div className="h-8 w-8 rounded-lg border border-indigo-800/40 bg-indigo-950/40 flex items-center justify-center">
            <CheckCircle className="h-3.5 w-3.5 text-indigo-400" />
          </div>
        ) : (
          <div className="h-8 w-8 rounded-lg border border-white/[0.06] bg-white/[0.03] flex items-center justify-center">
            <FileText className="h-3.5 w-3.5 text-zinc-600" />
          </div>
        )}
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0">
        <p className="text-sm text-zinc-200 truncate leading-tight font-medium">
          {session.title || "Untitled session"}
        </p>

        <div className="flex items-center gap-3 mt-1.5 flex-wrap">
          <span className="flex items-center gap-1 text-[11px] text-zinc-600">
            <Clock className="h-3 w-3" />
            {timeAgo(session.updatedAt)}
          </span>

          {session.figmaUrl && (
            <span className="flex items-center gap-1 text-[11px] text-emerald-600">
              <Figma className="h-3 w-3" />
              Figma
            </span>
          )}

          {issueCount && (
            <span className="flex items-center gap-1 text-[11px] text-zinc-600">
              <AlertTriangle className="h-3 w-3" />
              {issueCount.total} issues
            </span>
          )}
        </div>

        {/* Severity breakdown */}
        {issueCount && issueCount.total > 0 && (
          <div className="flex items-center gap-2 mt-2">
            {issueCount.critical > 0 && (
              <span className="rounded-md border border-red-800/40 bg-red-950/40 px-1.5 py-0.5 text-[10px] text-red-400 font-medium">
                {issueCount.critical} critical
              </span>
            )}
            {issueCount.high > 0 && (
              <span className="rounded-md border border-orange-800/40 bg-orange-950/40 px-1.5 py-0.5 text-[10px] text-orange-400 font-medium">
                {issueCount.high} high
              </span>
            )}
            {issueCount.medium > 0 && (
              <span className="rounded-md border border-amber-800/40 bg-amber-950/40 px-1.5 py-0.5 text-[10px] text-amber-400 font-medium">
                {issueCount.medium} med
              </span>
            )}
            {issueCount.low > 0 && (
              <span className="rounded-md border border-zinc-700/40 bg-zinc-900/40 px-1.5 py-0.5 text-[10px] text-zinc-500 font-medium">
                {issueCount.low} low
              </span>
            )}
          </div>
        )}
      </div>

      <ChevronRight className="h-4 w-4 text-zinc-700 group-hover:text-zinc-500 transition-colors shrink-0 mt-1" />
    </button>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function HistoryPage() {
  const router = useRouter();
  const [summaries, setSummaries] = useState<SessionSummary[]>([]);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    const sessions = loadSessions();
    const enriched: SessionSummary[] = sessions.map(s => {
      const messages = loadMessages(s.id);
      const issueCount = extractIssueSummary(messages);
      const hasCritique = messages.some(m => m.critiqueData != null);
      return { ...s, issueCount, hasCritique };
    });
    setSummaries(enriched);
    setLoaded(true);
  }, []);

  const groups = groupByDate(summaries);
  const totalCritiques = summaries.filter(s => s.hasCritique).length;
  const totalIssues = summaries.reduce((acc, s) => acc + (s.issueCount?.total ?? 0), 0);
  const criticalIssues = summaries.reduce((acc, s) => acc + (s.issueCount?.critical ?? 0), 0);

  return (
    <div className="flex flex-col h-full bg-zinc-950 overflow-y-auto">
      {/* Header */}
      <div className="border-b border-white/[0.06] px-6 h-[56px] flex items-center shrink-0">
        <p className="text-sm font-medium text-zinc-400">Evidence Log</p>
      </div>

      <div className="flex-1 px-6 py-6 max-w-3xl w-full mx-auto">
        <div className="mb-5">
          <h1 className="text-base font-semibold text-zinc-100">Design evidence log</h1>
          <p className="mt-1 text-sm text-zinc-500 leading-relaxed">
            A living record of every critique — issues found, what works, and how your designs evolve.
          </p>
        </div>

        {/* Stats row */}
        {loaded && summaries.length > 0 && (
          <div className="grid grid-cols-3 gap-3 mb-6">
            <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] px-4 py-3">
              <p className="text-[11px] text-zinc-600 uppercase tracking-wider font-medium">Sessions</p>
              <p className="text-2xl font-semibold text-zinc-100 mt-0.5">{summaries.length}</p>
            </div>
            <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] px-4 py-3">
              <p className="text-[11px] text-zinc-600 uppercase tracking-wider font-medium">Critiques</p>
              <p className="text-2xl font-semibold text-indigo-400 mt-0.5">{totalCritiques}</p>
            </div>
            <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] px-4 py-3">
              <p className="text-[11px] text-zinc-600 uppercase tracking-wider font-medium">Issues found</p>
              <p className="text-2xl font-semibold mt-0.5">
                <span className={criticalIssues > 0 ? "text-red-400" : "text-zinc-100"}>{totalIssues}</span>
              </p>
            </div>
          </div>
        )}

        {/* Timeline */}
        {!loaded ? (
          <div className="flex items-center justify-center py-16">
            <div className="h-5 w-5 rounded-full border-2 border-indigo-500 border-t-transparent animate-spin" />
          </div>
        ) : summaries.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 gap-3 text-center">
            <div className="h-10 w-10 rounded-xl border border-white/[0.06] bg-white/[0.02] flex items-center justify-center">
              <Clock className="h-5 w-5 text-zinc-700" />
            </div>
            <p className="text-sm text-zinc-500">No critiques yet</p>
            <p className="text-xs text-zinc-700">
              Run your first critique from the{" "}
              <button onClick={() => router.push("/")} className="text-indigo-400 hover:text-indigo-300 underline underline-offset-2">
                Critique
              </button>{" "}
              or{" "}
              <button onClick={() => router.push("/playbooks")} className="text-indigo-400 hover:text-indigo-300 underline underline-offset-2">
                Playbooks
              </button>{" "}
              page.
            </p>
          </div>
        ) : (
          <div className="space-y-6">
            {groups.map(({ label, items }) => (
              <div key={label}>
                <p className="text-[11px] text-zinc-700 uppercase tracking-wider font-medium mb-2">{label}</p>
                <div className="space-y-2">
                  {items.map(session => (
                    <SessionRow
                      key={session.id}
                      session={session}
                      onClick={() => router.push(`/?s=${session.id}`)}
                    />
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

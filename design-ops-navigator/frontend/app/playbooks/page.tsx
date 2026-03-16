"use client";

import Link from "next/link";
import { ArrowRight, Eye, Brain, UserCheck, Smartphone, TrendingUp } from "lucide-react";
import { PLAYBOOKS, Playbook } from "../lib/playbooks";

const ICONS: Record<string, React.ElementType> = {
  "accessibility-audit": Eye,
  "cognitive-load-check": Brain,
  "first-time-user-flow": UserCheck,
  "mobile-usability": Smartphone,
  "conversion-friction": TrendingUp,
};

const BADGE_STYLES: Record<string, string> = {
  indigo: "bg-indigo-950/60 text-indigo-400 border-indigo-800/40",
  violet: "bg-violet-950/60 text-violet-400 border-violet-800/40",
  emerald: "bg-emerald-950/60 text-emerald-400 border-emerald-800/40",
  amber: "bg-amber-950/60 text-amber-400 border-amber-800/40",
  rose: "bg-rose-950/60 text-rose-400 border-rose-800/40",
};

const BORDER_HOVER: Record<string, string> = {
  indigo: "hover:border-indigo-500/30",
  violet: "hover:border-violet-500/30",
  emerald: "hover:border-emerald-500/30",
  amber: "hover:border-amber-500/30",
  rose: "hover:border-rose-500/30",
};

function PlaybookCard({ playbook }: { playbook: Playbook }) {
  const Icon = ICONS[playbook.id] ?? Eye;
  const badgeStyle = BADGE_STYLES[playbook.badgeColor] ?? BADGE_STYLES.indigo;
  const borderHover = BORDER_HOVER[playbook.badgeColor] ?? BORDER_HOVER.indigo;

  return (
    <Link
      href={`/?playbook=${playbook.id}`}
      className={`group flex flex-col gap-3 rounded-xl border border-white/[0.07] bg-white/[0.02] p-5 transition-all duration-150 ${borderHover} hover:bg-white/[0.04]`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-white/[0.08] bg-white/[0.04]">
          <Icon className="h-4 w-4 text-zinc-400" />
        </div>
        <span className={`rounded-md border px-2 py-0.5 text-[11px] font-medium ${badgeStyle}`}>
          {playbook.badge}
        </span>
      </div>

      <div className="flex-1">
        <h3 className="text-sm font-semibold text-zinc-100 leading-tight">{playbook.title}</h3>
        <p className="mt-1.5 text-xs text-zinc-500 leading-relaxed">{playbook.description}</p>
      </div>

      <div className="flex items-center gap-1 text-xs text-zinc-600 group-hover:text-zinc-400 transition-colors">
        Run playbook
        <ArrowRight className="h-3 w-3 transition-transform group-hover:translate-x-0.5" />
      </div>
    </Link>
  );
}

export default function PlaybooksPage() {
  return (
    <div className="flex flex-col h-full bg-zinc-950 overflow-y-auto">
      <div className="border-b border-white/[0.06] px-6 h-[56px] flex items-center shrink-0">
        <p className="text-sm font-medium text-zinc-400">Playbooks</p>
      </div>

      <div className="flex-1 px-6 py-6 max-w-3xl w-full mx-auto">
        <div className="mb-6">
          <h1 className="text-base font-semibold text-zinc-100">Critique playbooks</h1>
          <p className="mt-1 text-sm text-zinc-500 leading-relaxed">
            Pre-built critique flows grounded in WCAG, Nielsen heuristics, and cognitive science.
            Select a playbook to pre-fill a tailored prompt — then add your Figma URL or screenshot and run.
          </p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {PLAYBOOKS.map(p => (
            <PlaybookCard key={p.id} playbook={p} />
          ))}
        </div>

        <div className="mt-8 rounded-xl border border-white/[0.06] bg-white/[0.02] px-5 py-4">
          <p className="text-xs font-medium text-zinc-400 mb-1">How playbooks work</p>
          <p className="text-xs text-zinc-600 leading-relaxed">
            Each playbook pre-fills a structured critique prompt in the chat. You can edit it before sending.
            Add a Figma frame URL or paste a screenshot to get visual analysis — or send without one
            for a general guidelines review.
          </p>
        </div>
      </div>
    </div>
  );
}

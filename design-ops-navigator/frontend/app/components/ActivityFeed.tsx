"use client";

import { AgentEvent } from "../hooks/useAgentStream";

const TOOL_LABELS: Record<string, string> = {
  search_knowledge_base: "Searching knowledge base",
  get_figma_node_tree: "Fetching Figma node tree",
  get_figma_frame_image: "Rendering Figma frame",
  parse_critique_json: "Validating critique schema",
  get_critique_schema: "Loading critique schema",
};

const STATE_LABELS: Record<string, string> = {
  figma_url: "Figma URL received",
  retrieved_knowledge: "Knowledge retrieved",
  figma_context: "Figma data loaded",
  critique_report: "Critique complete",
};

const AGENT_COLORS: Record<string, string> = {
  retriever_agent: "text-blue-400",
  figma_fetcher_agent: "text-violet-400",
  critic_agent: "text-amber-400",
  design_ops_navigator: "text-emerald-400",
};

function EventRow({ event }: { event: AgentEvent }) {
  const agentColor = event.agent ? (AGENT_COLORS[event.agent] ?? "text-zinc-400") : "text-zinc-400";
  const agentShort = event.agent?.replace("_agent", "").replace("design_ops_navigator", "orchestrator");

  if (event.type === "TOOL_CALL_START") {
    const label = TOOL_LABELS[event.tool ?? ""] ?? event.tool;
    return (
      <div className="flex items-start gap-2 py-1">
        <span className="mt-0.5 h-2 w-2 shrink-0 rounded-full bg-blue-500 animate-pulse" />
        <div className="min-w-0">
          <span className={`text-xs font-medium ${agentColor}`}>{agentShort}</span>
          <span className="mx-1 text-zinc-500 text-xs">→</span>
          <span className="text-xs text-zinc-300">{label}</span>
        </div>
      </div>
    );
  }

  if (event.type === "TOOL_CALL_END") {
    const label = TOOL_LABELS[event.tool ?? ""] ?? event.tool;
    const ok = event.status === "ok";
    return (
      <div className="flex items-start gap-2 py-1">
        <span className={`mt-0.5 shrink-0 text-xs ${ok ? "text-emerald-500" : "text-red-500"}`}>
          {ok ? "✓" : "✗"}
        </span>
        <span className="text-xs text-zinc-500">{label} done</span>
      </div>
    );
  }

  if (event.type === "STATE_DELTA" && event.key) {
    const label = STATE_LABELS[event.key] ?? event.key;
    return (
      <div className="flex items-start gap-2 py-1">
        <span className="mt-0.5 shrink-0 text-xs text-zinc-500">→</span>
        <span className="text-xs text-zinc-400 italic">{label}</span>
      </div>
    );
  }

  return null;
}

interface ActivityFeedProps {
  events: AgentEvent[];
  isRunning: boolean;
  compact?: boolean;
}

export function ActivityFeed({ events, isRunning, compact = false }: ActivityFeedProps) {
  if (events.length === 0 && !isRunning) return null;

  if (compact) {
    // Horizontal scrolling strip for inline use above chat
    const latest = events.slice(-6);
    return (
      <div className="flex items-center gap-3 overflow-x-auto no-scrollbar">
        {isRunning && (
          <span className="shrink-0 h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" />
        )}
        {latest.length === 0 && isRunning && (
          <span className="text-xs text-zinc-500 animate-pulse shrink-0">Starting agents…</span>
        )}
        {latest.map((e, i) => (
          <span key={i} className="shrink-0">
            <EventRow event={e} />
          </span>
        ))}
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-zinc-800 bg-zinc-900/60 p-3">
      <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-zinc-500">
        Agent Activity
        {isRunning && <span className="ml-2 inline-block h-1.5 w-1.5 rounded-full bg-emerald-400 animate-ping" />}
      </p>
      <div className="space-y-0.5">
        {events.map((e, i) => <EventRow key={i} event={e} />)}
        {isRunning && events.length === 0 && (
          <p className="text-xs text-zinc-500 animate-pulse">Starting agents…</p>
        )}
      </div>
    </div>
  );
}

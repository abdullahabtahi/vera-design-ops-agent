"use client";

import { AgentEvent } from "../hooks/useAgentStream";

const TOOL_LABELS: Record<string, string> = {
  search_knowledge_base: "Searching knowledge base",
  get_figma_node_tree: "Fetching Figma node tree",
  get_figma_frame_image: "Rendering Figma frame",
  parse_critique_json: "Validating critique schema",
  get_critique_schema: "Loading critique schema",
};

const AGENT_META: Record<string, { label: string; color: string; dot: string }> = {
  retriever_agent: { label: "Retriever", color: "text-blue-400", dot: "bg-blue-500" },
  figma_fetcher_agent: { label: "Figma", color: "text-violet-400", dot: "bg-violet-500" },
  critic_agent: { label: "Critic", color: "text-amber-400", dot: "bg-amber-500" },
  design_ops_navigator: { label: "Orchestrator", color: "text-emerald-400", dot: "bg-emerald-500" },
};

function EventRow({ event }: { event: AgentEvent }) {
  const meta = event.agent ? (AGENT_META[event.agent] ?? { label: event.agent, color: "text-zinc-400", dot: "bg-zinc-500" }) : null;

  if (event.type === "TOOL_CALL_START") {
    const label = TOOL_LABELS[event.tool ?? ""] ?? event.tool ?? "Unknown tool";
    return (
      <div className="flex items-start gap-2.5 py-1.5">
        <span className={`mt-1 h-1.5 w-1.5 shrink-0 rounded-full ${meta?.dot ?? "bg-zinc-500"} animate-pulse`} />
        <div className="min-w-0">
          {meta && <span className={`text-[11px] font-medium ${meta.color}`}>{meta.label}</span>}
          <p className="text-xs text-zinc-300 leading-snug">{label}</p>
        </div>
      </div>
    );
  }

  if (event.type === "TOOL_CALL_END") {
    const label = TOOL_LABELS[event.tool ?? ""] ?? event.tool ?? "Unknown tool";
    const ok = event.status === "ok";
    return (
      <div className="flex items-start gap-2.5 py-1">
        <span className={`mt-0.5 shrink-0 text-xs leading-none ${ok ? "text-emerald-500" : "text-red-500"}`}>
          {ok ? "✓" : "✗"}
        </span>
        <p className="text-xs text-zinc-600">{label} done</p>
      </div>
    );
  }

  if (event.type === "STATE_DELTA" && event.key) {
    const STATE_LABELS: Record<string, string> = {
      figma_url: "Figma URL received",
      retrieved_knowledge: "Knowledge retrieved",
      figma_context: "Figma data loaded",
      critique_report: "Critique complete",
      figma_frame_loaded: event.available ? "Figma frame rendered" : "Figma frame unavailable",
      screenshot_loaded: "Screenshot attached",
    };
    const label = STATE_LABELS[event.key] ?? event.key;
    const isUnavailable = event.key === "figma_frame_loaded" && !event.available;
    return (
      <div className="flex items-center gap-2 py-1">
        <span className="h-px flex-1 bg-white/[0.06]" />
        <p className={`text-[11px] italic shrink-0 ${isUnavailable ? "text-amber-700" : "text-zinc-600"}`}>
          {label}
        </p>
        <span className="h-px flex-1 bg-white/[0.06]" />
      </div>
    );
  }

  return null;
}

interface AgentPanelProps {
  events: AgentEvent[];
  isRunning: boolean;
}

export function AgentPanel({ events, isRunning }: AgentPanelProps) {
  if (events.length === 0 && !isRunning) return null;

  // Count active agents
  const activeAgents = new Set(
    events
      .filter(e => e.type === "TOOL_CALL_START" && e.agent)
      .map(e => e.agent!)
  );

  return (
    <div className="w-[260px] shrink-0 flex flex-col border-l border-white/[0.06] bg-[#0c0c0d]">
      {/* Header */}
      <div className="flex items-center justify-between px-4 h-[56px] border-b border-white/[0.06] shrink-0">
        <div className="flex items-center gap-2">
          <span className={`h-1.5 w-1.5 rounded-full ${isRunning ? "bg-emerald-400 animate-pulse" : "bg-zinc-600"}`} />
          <span className="text-[12px] font-semibold text-zinc-400 uppercase tracking-wider">
            Agent Activity
          </span>
        </div>
        {isRunning && (
          <span className="text-[11px] text-emerald-500 animate-pulse">Running</span>
        )}
      </div>

      {/* Active agents chips */}
      {isRunning && activeAgents.size > 0 && (
        <div className="flex flex-wrap gap-1.5 px-4 py-2.5 border-b border-white/[0.04]">
          {[...activeAgents].map(agent => {
            const meta = AGENT_META[agent] ?? { label: agent, color: "text-zinc-400", dot: "bg-zinc-600" };
            return (
              <span key={agent} className={`flex items-center gap-1 rounded-full border border-white/[0.06] bg-white/[0.03] px-2 py-0.5 text-[11px] ${meta.color}`}>
                <span className={`h-1 w-1 rounded-full ${meta.dot}`} />
                {meta.label}
              </span>
            );
          })}
        </div>
      )}

      {/* Events */}
      <div className="flex-1 overflow-y-auto px-4 py-3 space-y-0">
        {events.length === 0 && isRunning && (
          <div className="flex items-center gap-2 py-2">
            <span className="h-1 w-1 rounded-full bg-zinc-600 animate-bounce" style={{ animationDelay: "0ms" }} />
            <span className="h-1 w-1 rounded-full bg-zinc-600 animate-bounce" style={{ animationDelay: "150ms" }} />
            <span className="h-1 w-1 rounded-full bg-zinc-600 animate-bounce" style={{ animationDelay: "300ms" }} />
            <span className="text-xs text-zinc-600 ml-1">Starting agents…</span>
          </div>
        )}
        {events.map((e, i) => <EventRow key={i} event={e} />)}
      </div>

      {/* Footer stats */}
      {events.length > 0 && (
        <div className="border-t border-white/[0.04] px-4 py-2.5 flex items-center gap-3">
          <span className="text-[11px] text-zinc-700">
            {events.filter(e => e.type === "TOOL_CALL_END" && e.status === "ok").length} tools done
          </span>
          <span className="h-1 w-1 rounded-full bg-zinc-800" />
          <span className="text-[11px] text-zinc-700">
            {events.length} events
          </span>
        </div>
      )}
    </div>
  );
}

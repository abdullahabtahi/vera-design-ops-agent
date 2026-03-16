"use client";

import { useState, useEffect, useRef, Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { ChevronDown, ChevronUp, Target, X, KeyRound, CheckCircle2 } from "lucide-react";
import { loadWorkspaces, createWorkspace, WorkspaceMeta, getFigmaToken, saveFigmaToken } from "./hooks/useAgentStream";
import { useAgentContext } from "./contexts/AgentContext";
import { ChatWindow } from "./components/ChatWindow";
import { AgentPanel } from "./components/AgentPanel";
import { getPlaybook, Playbook } from "./lib/playbooks";

// ── Project context panel ─────────────────────────────────────────────────────

export interface ProjectContext {
  goal: string;
  persona: string;
  environment: string;
}

function ProjectContextPanel({
  value,
  onChange,
}: {
  value: ProjectContext;
  onChange: (v: ProjectContext) => void;
}) {
  const [open, setOpen] = useState(false);
  const hasContext = value.goal || value.persona || value.environment;

  return (
    <div className="border-b border-white/[0.06] px-4 shrink-0">
      <button
        onClick={() => setOpen(p => !p)}
        className="flex items-center gap-1.5 py-1.5 text-[11px] text-zinc-600 hover:text-zinc-400 transition-colors"
      >
        {open ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
        <Target className="h-3 w-3" />
        {hasContext ? (
          <span className="text-indigo-400">Project context set</span>
        ) : (
          "Add project context (optional)"
        )}
      </button>
      {open && (
        <div className="pb-3 space-y-2">
          <p className="text-[11px] text-zinc-700 mb-2">
            Provide context so the critique is grounded in your actual goals and users.
          </p>
          <input
            type="text"
            placeholder="Goal — e.g. reduce checkout abandonment, increase sign-up conversion"
            value={value.goal}
            onChange={e => onChange({ ...value, goal: e.target.value })}
            className="w-full bg-zinc-900 border border-white/[0.07] rounded-lg px-3 py-1.5 text-xs text-zinc-300 placeholder-zinc-700 focus:outline-none focus:border-indigo-500/50"
          />
          <input
            type="text"
            placeholder="Persona — e.g. first-time mobile shopper, 25–35, low tech literacy"
            value={value.persona}
            onChange={e => onChange({ ...value, persona: e.target.value })}
            className="w-full bg-zinc-900 border border-white/[0.07] rounded-lg px-3 py-1.5 text-xs text-zinc-300 placeholder-zinc-700 focus:outline-none focus:border-indigo-500/50"
          />
          <input
            type="text"
            placeholder="Environment — e.g. iPhone 15, bright outdoor use, low bandwidth"
            value={value.environment}
            onChange={e => onChange({ ...value, environment: e.target.value })}
            className="w-full bg-zinc-900 border border-white/[0.07] rounded-lg px-3 py-1.5 text-xs text-zinc-300 placeholder-zinc-700 focus:outline-none focus:border-indigo-500/50"
          />
        </div>
      )}
    </div>
  );
}

// ── Design URL field (Figma or live website) ──────────────────────────────────

function FigmaUrlField({
  value,
  onChange,
}: {
  value: string;
  onChange: (v: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const isFigma = value.includes("figma.com");
  const isWebsite = value.startsWith("http") && !isFigma;
  const hasUrl = isFigma || isWebsite;

  const statusLabel = isFigma
    ? <span className="text-emerald-500">Figma frame attached</span>
    : isWebsite
    ? <span className="text-sky-400">Live website attached</span>
    : "Add design URL (optional)";

  const borderClass = isFigma
    ? "border-emerald-700/50 bg-emerald-950/10"
    : isWebsite
    ? "border-sky-700/50 bg-sky-950/10"
    : "border-white/[0.07] bg-white/[0.02]";

  return (
    <div className="border-b border-white/[0.06] px-4 shrink-0">
      <button
        onClick={() => setOpen(p => !p)}
        className="flex items-center gap-1.5 py-1.5 text-[11px] text-zinc-600 hover:text-zinc-400 transition-colors"
      >
        {open ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
        {statusLabel}
      </button>
      {open && (
        <div className="pb-2">
          <div className={`flex items-center gap-2 rounded-lg border px-3 py-1.5 transition-colors ${borderClass}`}>
            {isFigma ? (
              <svg width="10" height="15" viewBox="0 0 38 57" fill="none" className="shrink-0">
                <path d="M19 28.5a9.5 9.5 0 1 1 19 0 9.5 9.5 0 0 1-19 0z" fill="#1abcfe" />
                <path d="M0 47.5A9.5 9.5 0 0 1 9.5 38H19v9.5a9.5 9.5 0 0 1-19 0z" fill="#0acf83" />
                <path d="M19 0v19h9.5a9.5 9.5 0 0 0 0-19H19z" fill="#ff7262" />
                <path d="M0 9.5A9.5 9.5 0 0 0 9.5 19H19V0H9.5A9.5 9.5 0 0 0 0 9.5z" fill="#f24e1e" />
                <path d="M0 28.5A9.5 9.5 0 0 0 9.5 38H19V19H9.5A9.5 9.5 0 0 0 0 28.5z" fill="#a259ff" />
              </svg>
            ) : (
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke={isWebsite ? "#38bdf8" : "#52525b"} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="shrink-0">
                <circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/>
                <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>
              </svg>
            )}
            <input
              type="url"
              value={value}
              onChange={e => onChange(e.target.value)}
              placeholder="https://figma.com/design/…  or  https://yoursite.com"
              className="flex-1 bg-transparent text-xs text-zinc-300 placeholder-zinc-700 focus:outline-none"
            />
            {hasUrl && value && (
              <button
                onClick={() => onChange("")}
                className="text-zinc-600 hover:text-zinc-400 text-xs"
              >
                ✕
              </button>
            )}
          </div>
          <p className="text-[11px] text-zinc-700 mt-1">
            Paste a Figma URL with ?node-id= or any live website URL — a screenshot is captured automatically.
          </p>
        </div>
      )}
    </div>
  );
}

// ── Workspace picker ──────────────────────────────────────────────────────────

const WORKSPACE_COLORS: Record<WorkspaceMeta["color"], string> = {
  indigo: "bg-indigo-500",
  violet: "bg-violet-500",
  emerald: "bg-emerald-500",
  amber: "bg-amber-500",
  rose: "bg-rose-500",
};

function WorkspacePicker({
  workspaces,
  activeId,
  onSelect,
  onRefresh,
}: {
  workspaces: WorkspaceMeta[];
  activeId: string | undefined;
  onSelect: (id: string | undefined) => void;
  onRefresh: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [newName, setNewName] = useState("");

  function handleCreate(name: string) {
    const ws = createWorkspace(name);
    onRefresh();
    onSelect(ws.id);
  }
  const active = workspaces.find(w => w.id === activeId);

  return (
    <div className="relative">
      <button
        onClick={() => setOpen(p => !p)}
        className="flex items-center gap-1.5 rounded-lg px-2.5 py-1 text-[11px] border border-white/[0.07] bg-white/[0.02] text-zinc-500 hover:text-zinc-300 hover:border-white/[0.12] transition-colors"
      >
        {active ? (
          <>
            <span className={`h-1.5 w-1.5 rounded-full ${WORKSPACE_COLORS[active.color]}`} />
            <span className="max-w-[80px] truncate">{active.name}</span>
          </>
        ) : (
          <span>No project</span>
        )}
      </button>

      {open && (
        <>
          <div className="fixed inset-0 z-10" onClick={() => setOpen(false)} />
          <div className="absolute right-0 top-full mt-1 z-20 w-48 rounded-xl border border-white/[0.1] bg-zinc-900 shadow-2xl overflow-hidden">
            <div className="p-1">
              <button
                onClick={() => { onSelect(undefined); setOpen(false); }}
                className={`w-full flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs text-left transition-colors ${
                  !activeId ? "bg-white/[0.08] text-zinc-200" : "text-zinc-400 hover:bg-white/[0.04] hover:text-zinc-200"
                }`}
              >
                No project
              </button>
              {workspaces.map(ws => (
                <button
                  key={ws.id}
                  onClick={() => { onSelect(ws.id); setOpen(false); }}
                  className={`w-full flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs text-left transition-colors ${
                    activeId === ws.id ? "bg-white/[0.08] text-zinc-200" : "text-zinc-400 hover:bg-white/[0.04] hover:text-zinc-200"
                  }`}
                >
                  <span className={`h-1.5 w-1.5 rounded-full shrink-0 ${WORKSPACE_COLORS[ws.color]}`} />
                  <span className="truncate">{ws.name}</span>
                </button>
              ))}
            </div>
            <div className="border-t border-white/[0.06] p-2">
              <form
                onSubmit={e => {
                  e.preventDefault();
                  const name = newName.trim();
                  if (!name) return;
                  handleCreate(name);
                  setNewName("");
                  setOpen(false);
                }}
                className="flex gap-1"
              >
                <input
                  type="text"
                  value={newName}
                  onChange={e => setNewName(e.target.value)}
                  placeholder="New project…"
                  className="flex-1 min-w-0 bg-white/[0.04] border border-white/[0.07] rounded-lg px-2 py-1 text-xs text-zinc-300 placeholder-zinc-700 focus:outline-none focus:border-indigo-500/50"
                />
                <button
                  type="submit"
                  disabled={!newName.trim()}
                  className="shrink-0 rounded-lg bg-indigo-600 px-2 py-1 text-xs text-white hover:bg-indigo-500 disabled:opacity-40 transition-colors"
                >
                  Add
                </button>
              </form>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

// ── Figma setup banner (shown to new users) ────────────────────────────────────

function FigmaSetupBanner({ onDone }: { onDone: () => void }) {
  const [draft, setDraft] = useState("");
  const [saved, setSaved] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  function handleSave() {
    if (draft.trim()) {
      saveFigmaToken(draft.trim());
      setSaved(true);
      setTimeout(onDone, 900);
    }
  }

  return (
    <div className="mx-4 mt-3 shrink-0 rounded-xl border border-amber-800/40 bg-amber-950/20 p-4">
      <div className="flex items-start gap-3">
        <div className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-amber-950/60 border border-amber-800/40">
          {saved ? (
            <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" />
          ) : (
            <KeyRound className="h-3.5 w-3.5 text-amber-400" />
          )}
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-[13px] font-medium text-amber-300 leading-tight">
            {saved ? "Figma connected!" : "Connect your Figma account"}
          </p>
          <p className="text-[11px] text-amber-700 mt-0.5 leading-relaxed">
            Add your Personal Access Token to critique Figma designs directly. Get it from{" "}
            <span className="text-amber-600">Figma → Settings → Security → Personal access tokens</span>.
          </p>
          {!saved && (
            <div className="flex gap-2 mt-2.5">
              <input
                ref={inputRef}
                type="password"
                value={draft}
                onChange={e => setDraft(e.target.value)}
                onKeyDown={e => { if (e.key === "Enter") handleSave(); }}
                placeholder="figd_…"
                className="flex-1 min-w-0 bg-zinc-900 border border-white/[0.07] rounded-lg px-2.5 py-1.5 text-[11px] text-zinc-300 placeholder-zinc-700 focus:outline-none focus:border-amber-500/50"
              />
              <button
                onClick={handleSave}
                disabled={!draft.trim()}
                className="shrink-0 rounded-lg bg-amber-600 px-3 py-1.5 text-[11px] text-white font-medium hover:bg-amber-500 disabled:opacity-40 transition-colors"
              >
                Connect
              </button>
              <button
                onClick={onDone}
                className="shrink-0 rounded-lg border border-white/[0.07] px-3 py-1.5 text-[11px] text-zinc-600 hover:text-zinc-400 transition-colors"
              >
                Skip
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Playbook banner ───────────────────────────────────────────────────────────

function PlaybookBanner({ playbook, onDismiss }: { playbook: Playbook; onDismiss: () => void }) {
  return (
    <div className="flex items-center gap-2 border-b border-indigo-900/40 bg-indigo-950/20 px-4 py-1.5 shrink-0">
      <span className="text-[11px] text-indigo-400 font-medium">Playbook:</span>
      <span className="text-[11px] text-indigo-300">{playbook.title}</span>
      <span className="ml-auto text-[11px] text-indigo-600">Edit the prompt below, then send</span>
      <button onClick={onDismiss} className="text-indigo-700 hover:text-indigo-400 transition-colors ml-1">
        <X className="h-3 w-3" />
      </button>
    </div>
  );
}

// ── Home (wrapped for useSearchParams) ───────────────────────────────────────

function HomeInner() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const sessionParam = searchParams.get("s");
  const playbookParam = searchParams.get("playbook");

  const playbook: Playbook | undefined = playbookParam ? getPlaybook(playbookParam) : undefined;

  const [workspaces, setWorkspaces] = useState<WorkspaceMeta[]>([]);
  const [showPlaybookBanner, setShowPlaybookBanner] = useState(!!playbook);

  useEffect(() => {
    setWorkspaces(loadWorkspaces());
  }, []);

  // Re-show banner when playbook param changes (e.g. navigating between playbooks)
  useEffect(() => {
    setShowPlaybookBanner(!!playbook);
  }, [playbookParam]); // eslint-disable-line react-hooks/exhaustive-deps

  // Agent stream state lives in AgentContext so it survives sidebar navigation
  const {
    messages, activity, isRunning, error, send, stop, reset, loadSession, sessionId,
    figmaUrl, setFigmaUrl,
    activeWorkspaceId, setActiveWorkspaceId,
  } = useAgentContext();

  const [projectContext, setProjectContext] = useState<ProjectContext>({ goal: "", persona: "", environment: "" });
  const showAgentPanel = isRunning || activity.length > 0;

  // Figma setup banner: show once for new users with no token and no sessions
  const [showFigmaSetup, setShowFigmaSetup] = useState(false);
  useEffect(() => {
    if (typeof window === "undefined") return;
    const hasToken = !!getFigmaToken();
    const hasSessions = (() => { try { return JSON.parse(localStorage.getItem("don.sessions") ?? localStorage.getItem(`don.${localStorage.getItem("don.uid") ?? ""}.sessions`) ?? "[]").length > 0; } catch { return false; } })();
    setShowFigmaSetup(!hasToken && !hasSessions);
  }, []);

  // ?new=1: "New critique" button signals a fresh session (avoids ambiguity with nav clicks)
  const newParam = searchParams.get("new");
  useEffect(() => {
    if (newParam) {
      reset();
      router.replace("/", { scroll: false });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [newParam]);

  // When sessionId updates from URL param change, load that session
  useEffect(() => {
    if (sessionParam && sessionParam !== sessionId) {
      loadSession(sessionParam);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionParam]);

  // Keep URL in sync with active session so refresh restores it
  useEffect(() => {
    if (sessionId && !sessionParam) {
      router.replace(`/?s=${sessionId}`, { scroll: false });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId]);

  function handleSend(text: string, image?: File | null) {
    let effectiveFigmaUrl = figmaUrl;
    if (!effectiveFigmaUrl) {
      const m = text.match(/https:\/\/(?:www\.)?figma\.com\/[^\s)]+/);
      if (m) effectiveFigmaUrl = m[0];
    }

    const ctx = projectContext;
    const parts = [
      ctx.goal        && `Goal: ${ctx.goal}`,
      ctx.persona     && `Persona: ${ctx.persona}`,
      ctx.environment && `Environment: ${ctx.environment}`,
    ].filter(Boolean);
    const prefix = parts.length ? `[Project context — ${parts.join(" | ")}]\n\n` : "";
    send(prefix + text, effectiveFigmaUrl || undefined, image);

    // Clear playbook param from URL after first send
    if (playbookParam) {
      setShowPlaybookBanner(false);
      router.replace("/", { scroll: false });
    }
  }

  function handleReset() {
    reset();
    router.push("/");
  }

  return (
    <div className="flex h-full bg-zinc-950">
      {/* Main column */}
      <div className="flex flex-col flex-1 min-w-0">
        {/* Top status bar */}
        <div className="flex items-center justify-between border-b border-white/[0.06] px-4 h-[56px] shrink-0">
          <p className="text-sm font-medium text-zinc-400">
            {messages.length === 0 ? "New critique" : "Design critique"}
          </p>
          <div className="flex items-center gap-3">
            <WorkspacePicker
              workspaces={workspaces}
              activeId={activeWorkspaceId}
              onSelect={setActiveWorkspaceId}
              onRefresh={() => setWorkspaces(loadWorkspaces())}
            />
            {isRunning ? (
              <button
                onClick={stop}
                aria-label="Stop agent"
                className="text-xs text-red-500 hover:text-red-400 border border-red-900/40 rounded-md px-2 py-0.5 transition-colors"
              >
                Stop
              </button>
            ) : messages.length > 0 && (
              <button
                onClick={handleReset}
                className="text-xs text-zinc-600 hover:text-zinc-300 transition-colors"
              >
                New chat
              </button>
            )}
            <div className="flex items-center gap-1.5">
              <span className={`h-1.5 w-1.5 rounded-full ${isRunning ? "bg-emerald-400 animate-pulse" : "bg-zinc-700"}`} />
              <span className="text-xs text-zinc-600">{isRunning ? "Running" : "Ready"}</span>
            </div>
          </div>
        </div>

        {/* Playbook banner */}
        {playbook && showPlaybookBanner && messages.length === 0 && (
          <PlaybookBanner playbook={playbook} onDismiss={() => setShowPlaybookBanner(false)} />
        )}

        {/* Project context — collapsible */}
        <ProjectContextPanel value={projectContext} onChange={setProjectContext} />

        {/* Figma URL — secondary, collapsible */}
        <FigmaUrlField value={figmaUrl} onChange={setFigmaUrl} />

        {/* First-run Figma setup prompt */}
        {showFigmaSetup && messages.length === 0 && (
          <FigmaSetupBanner onDone={() => setShowFigmaSetup(false)} />
        )}

        {/* Error */}
        {error && (
          <div className="mx-4 mt-2 rounded-lg border border-red-900/50 bg-red-950/30 px-3 py-2 shrink-0">
            <p className="text-xs text-red-400">{error}</p>
          </div>
        )}

        {/* Chat */}
        <div className="flex-1 min-h-0">
          <ChatWindow
            messages={messages}
            isRunning={isRunning}
            onSend={handleSend}
            initialInput={playbook?.prompt}
            figmaUrl={figmaUrl || undefined}
            sessionId={sessionId ?? undefined}
          />
        </div>
      </div>

      {/* Right agent panel */}
      {showAgentPanel && (
        <AgentPanel events={activity} isRunning={isRunning} />
      )}
    </div>
  );
}

export default function Home() {
  return (
    <Suspense fallback={<div className="flex h-full items-center justify-center bg-zinc-950" />}>
      <HomeInner />
    </Suspense>
  );
}

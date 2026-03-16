"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { MessageSquare, BookOpen, Plus, ChevronLeft, ChevronRight, Sparkles, Clock, Zap, History, FolderOpen, BarChart2, KeyRound, CheckCircle2, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useSidebar } from "./AppShell";
import { loadSessions, loadWorkspaces, SessionMeta, WorkspaceMeta, getFigmaToken, saveFigmaToken, clearFigmaToken } from "../hooks/useAgentStream";

const NAV = [
  { href: "/", label: "Critique", icon: MessageSquare },
  { href: "/playbooks", label: "Playbooks", icon: Zap },
  { href: "/history", label: "Evidence", icon: History },
  { href: "/dashboard", label: "Activity", icon: BarChart2 },
  { href: "/knowledge", label: "Knowledge", icon: BookOpen },
];

const WORKSPACE_DOT: Record<WorkspaceMeta["color"], string> = {
  indigo: "bg-indigo-500",
  violet: "bg-violet-500",
  emerald: "bg-emerald-500",
  amber: "bg-amber-500",
  rose: "bg-rose-500",
};

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

// ── Figma token widget ────────────────────────────────────────────────────────

function FigmaTokenWidget({ collapsed }: { collapsed: boolean }) {
  const [token, setToken] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    setToken(getFigmaToken());
  }, []);

  function openEdit() {
    setDraft(token ?? "");
    setEditing(true);
    setTimeout(() => inputRef.current?.focus(), 0);
  }

  function save() {
    if (draft.trim()) {
      saveFigmaToken(draft.trim());
      setToken(draft.trim());
    } else {
      clearFigmaToken();
      setToken(null);
    }
    setEditing(false);
  }

  function remove() {
    clearFigmaToken();
    setToken(null);
    setEditing(false);
  }

  if (collapsed) {
    return (
      <button
        onClick={openEdit}
        title={token ? "Figma connected" : "Add Figma token"}
        className="flex justify-center pb-3"
      >
        <div className={`h-2 w-2 rounded-full ${token ? "bg-emerald-500" : "bg-amber-500"}`} />
      </button>
    );
  }

  return (
    <div className="px-3 pb-3 shrink-0">
      {editing ? (
        <div className="rounded-xl border border-white/[0.07] bg-white/[0.02] p-2.5 space-y-2">
          <p className="text-[11px] text-zinc-500 leading-relaxed">
            Paste your Figma Personal Access Token.<br />
            <span className="text-zinc-700">Settings → Security → Personal access tokens</span>
          </p>
          <input
            ref={inputRef}
            type="password"
            value={draft}
            onChange={e => setDraft(e.target.value)}
            onKeyDown={e => { if (e.key === "Enter") save(); if (e.key === "Escape") setEditing(false); }}
            placeholder="figd_…"
            className="w-full bg-zinc-900 border border-white/[0.07] rounded-lg px-2.5 py-1.5 text-[11px] text-zinc-300 placeholder-zinc-700 focus:outline-none focus:border-indigo-500/50"
          />
          <div className="flex gap-1.5">
            <button
              onClick={save}
              className="flex-1 rounded-lg bg-indigo-600 px-2 py-1 text-[11px] text-white hover:bg-indigo-500 transition-colors"
            >
              Save
            </button>
            {token && (
              <button
                onClick={remove}
                className="rounded-lg border border-white/[0.07] px-2 py-1 text-[11px] text-zinc-500 hover:text-red-400 hover:border-red-900/40 transition-colors"
              >
                Remove
              </button>
            )}
            <button
              onClick={() => setEditing(false)}
              className="rounded-lg border border-white/[0.07] px-2 py-1 text-[11px] text-zinc-600 hover:text-zinc-400 transition-colors"
            >
              Cancel
            </button>
          </div>
        </div>
      ) : (
        <button
          onClick={openEdit}
          className={`w-full flex items-center gap-2 rounded-xl border px-3 py-2 transition-colors group ${
            token
              ? "border-emerald-800/40 bg-emerald-950/20 hover:border-emerald-700/50"
              : "border-amber-800/40 bg-amber-950/20 hover:border-amber-700/50"
          }`}
        >
          {token ? (
            <CheckCircle2 className="h-3.5 w-3.5 shrink-0 text-emerald-500" />
          ) : (
            <KeyRound className="h-3.5 w-3.5 shrink-0 text-amber-500" />
          )}
          <span className={`text-[11px] font-medium ${token ? "text-emerald-400" : "text-amber-400"}`}>
            {token ? "Figma connected" : "Add Figma token"}
          </span>
          {token && (
            <button
              onClick={e => { e.stopPropagation(); remove(); }}
              className="ml-auto text-zinc-700 hover:text-zinc-400 transition-colors opacity-0 group-hover:opacity-100"
              title="Disconnect"
            >
              <X className="h-3 w-3" />
            </button>
          )}
        </button>
      )}
    </div>
  );
}

export function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const { collapsed, toggle } = useSidebar();
  const [sessions, setSessions] = useState<SessionMeta[]>([]);
  const [workspaces, setWorkspaces] = useState<WorkspaceMeta[]>([]);
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);
  const [filterWorkspaceId, setFilterWorkspaceId] = useState<string | null>(null);

  useEffect(() => {
    setSessions(loadSessions().slice(0, 20));
    setWorkspaces(loadWorkspaces());
    setCurrentSessionId(new URLSearchParams(window.location.search).get("s"));
  }, [pathname]);

  const visibleSessions = filterWorkspaceId
    ? sessions.filter(s => s.workspaceId === filterWorkspaceId).slice(0, 8)
    : sessions.slice(0, 8);

  return (
    <aside
      className={`relative flex flex-col h-screen shrink-0 bg-[#0f0f10] border-r border-white/[0.06] transition-all duration-200 ease-in-out ${
        collapsed ? "w-12" : "w-[220px]"
      }`}
    >
      {/* Toggle button */}
      <button
        onClick={toggle}
        className="absolute -right-3 top-[22px] z-20 flex h-6 w-6 items-center justify-center rounded-full border border-white/10 bg-zinc-900 text-zinc-500 hover:text-zinc-200 hover:border-white/20 transition-colors shadow-md"
        aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
      >
        {collapsed ? <ChevronRight className="h-3 w-3" /> : <ChevronLeft className="h-3 w-3" />}
      </button>

      {/* Logo */}
      <div className={`flex items-center gap-2.5 h-[56px] shrink-0 px-3 border-b border-white/[0.06] ${collapsed ? "justify-center" : ""}`}>
        <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-gradient-to-br from-indigo-500 to-violet-600 shadow-lg shadow-indigo-900/30">
          <Sparkles className="h-3.5 w-3.5 text-white" />
        </div>
        {!collapsed && (
          <div className="min-w-0 overflow-hidden">
            <p className="text-[13px] font-semibold text-zinc-100 leading-tight truncate">Vera</p>
            <p className="text-[11px] text-zinc-600 truncate">Design Ops Agent</p>
          </div>
        )}
      </div>

      {/* New critique button — /?new=1 signals a fresh session to HomeInner */}
      <div className={`px-2 pt-3 pb-1 ${collapsed ? "flex justify-center" : ""}`}>
        {collapsed ? (
          <button
            onClick={() => router.push("/?new=1")}
            className="flex h-8 w-8 items-center justify-center rounded-lg text-zinc-500 hover:bg-white/[0.06] hover:text-zinc-300 transition-colors"
            title="New critique"
          >
            <Plus className="h-4 w-4" />
          </button>
        ) : (
          <button
            onClick={() => router.push("/?new=1")}
            className="flex items-center gap-2 w-full rounded-lg px-3 py-2 text-[13px] text-zinc-400 hover:bg-white/[0.05] hover:text-zinc-200 transition-colors group"
          >
            <Plus className="h-3.5 w-3.5 text-zinc-500 group-hover:text-zinc-300" />
            New critique
          </button>
        )}
      </div>

      {/* Divider */}
      <div className="mx-3 my-1 h-px bg-white/[0.05]" />

      {/* Nav */}
      <nav className={`px-2 pt-1 space-y-0.5 ${collapsed ? "flex flex-col items-center" : ""}`}>
        {NAV.map(({ href, label, icon: Icon }) => {
          const active = pathname === href && (href !== "/" || !currentSessionId);
          return (
            <Link
              key={href}
              href={href}
              title={collapsed ? label : undefined}
              className={`flex items-center gap-2.5 rounded-lg transition-colors ${
                collapsed ? "h-9 w-9 justify-center" : "px-3 py-2 w-full"
              } ${
                active
                  ? "bg-white/[0.08] text-zinc-100"
                  : "text-zinc-500 hover:bg-white/[0.04] hover:text-zinc-300"
              }`}
            >
              <Icon className={`h-4 w-4 shrink-0 ${active ? "text-zinc-200" : ""}`} />
              {!collapsed && <span className="text-[13px] font-medium">{label}</span>}
              {!collapsed && active && <span className="ml-auto h-1.5 w-1.5 rounded-full bg-indigo-400" />}
            </Link>
          );
        })}
      </nav>

      {/* Projects — only in expanded mode */}
      {!collapsed && workspaces.length > 0 && (
        <>
          <div className="mx-3 mt-3 mb-1 h-px bg-white/[0.05]" />
          <div className="px-2 pb-1">
            <div className="flex items-center gap-1.5 px-2 py-1.5">
              <FolderOpen className="h-3 w-3 text-zinc-700" />
              <p className="text-[11px] text-zinc-700 uppercase tracking-wider font-medium">Projects</p>
            </div>
            <div className="space-y-0.5">
              {workspaces.slice(0, 5).map(ws => {
                const isActive = filterWorkspaceId === ws.id;
                return (
                  <button
                    key={ws.id}
                    onClick={() => setFilterWorkspaceId(isActive ? null : ws.id)}
                    className={`w-full flex items-center gap-2 rounded-lg px-3 py-1.5 transition-colors text-left ${
                      isActive
                        ? "bg-white/[0.08] text-zinc-200"
                        : "text-zinc-500 hover:bg-white/[0.04] hover:text-zinc-300"
                    }`}
                  >
                    <span className={`h-1.5 w-1.5 rounded-full shrink-0 ${WORKSPACE_DOT[ws.color]}`} />
                    <span className="text-[12px] truncate">{ws.name}</span>
                  </button>
                );
              })}
            </div>
          </div>
        </>
      )}

      {/* Recent sessions — only in expanded mode */}
      {!collapsed && visibleSessions.length > 0 && (
        <>
          <div className="mx-3 mt-3 mb-1 h-px bg-white/[0.05]" />
          <div className="px-2 pb-1 overflow-y-auto flex-1 min-h-0">
            <div className="flex items-center gap-1.5 px-2 py-1.5">
              <Clock className="h-3 w-3 text-zinc-700" />
              <p className="text-[11px] text-zinc-700 uppercase tracking-wider font-medium">
                {filterWorkspaceId ? workspaces.find(w => w.id === filterWorkspaceId)?.name ?? "Recent" : "Recent"}
              </p>
            </div>
            <div className="space-y-0.5">
              {visibleSessions.map(s => {
                const isActive = currentSessionId === s.id;
                return (
                  <button
                    key={s.id}
                    onClick={() => router.push(`/?s=${s.id}`)}
                    className={`w-full flex flex-col items-start rounded-lg px-3 py-2 transition-colors text-left ${
                      isActive
                        ? "bg-white/[0.08] text-zinc-200"
                        : "text-zinc-500 hover:bg-white/[0.04] hover:text-zinc-300"
                    }`}
                  >
                    <span className="text-[12px] truncate w-full leading-tight">
                      {s.title || "Untitled session"}
                    </span>
                    <span className="text-[11px] text-zinc-700 mt-0.5">{timeAgo(s.updatedAt)}</span>
                  </button>
                );
              })}
            </div>
          </div>
        </>
      )}

      {/* Spacer (only if no scrollable sessions) */}
      {(collapsed || visibleSessions.length === 0) && <div className="flex-1" />}

      {/* Footer — session count + Figma token status */}
      <div className="border-t border-white/[0.05] shrink-0">
        {!collapsed && (
          <div className="px-3 pt-3 pb-2">
            <Link
              href="/dashboard"
              className="flex items-center justify-between group rounded-lg px-2 py-1.5 hover:bg-white/[0.04] transition-colors"
            >
              <span className="text-[11px] text-zinc-700 group-hover:text-zinc-500 transition-colors">
                {sessions.length > 0
                  ? `${sessions.length} session${sessions.length !== 1 ? "s" : ""}`
                  : "No sessions yet"}
              </span>
              <span className="text-[11px] text-indigo-700 group-hover:text-indigo-400 transition-colors">
                Dashboard →
              </span>
            </Link>
          </div>
        )}

        {/* Figma token status */}
        <FigmaTokenWidget collapsed={collapsed} />
      </div>

      {collapsed && (
        <div className="sr-only">
          {/* collapsed footer handled inside FigmaTokenWidget */}
        </div>
      )}
    </aside>
  );
}

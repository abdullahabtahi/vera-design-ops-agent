"use client";

/**
 * AgentContext — lifts useAgentStream + figmaUrl to the layout level.
 *
 * Why: useAgentStream previously lived in page.tsx, which unmounts on every
 * sidebar navigation. Moving it here ensures:
 *   - The SSE stream is NOT aborted when user navigates to /playbooks, /history, etc.
 *   - Messages, activity feed, and Figma URL persist across navigation.
 *   - The agent can finish its critique even while the user browses other pages.
 */

import { createContext, useContext, useState, useCallback, ReactNode } from "react";
import { useAgentStream } from "../hooks/useAgentStream";
import type { Message, AgentEvent } from "../hooks/useAgentStream";

export interface AgentContextValue {
  // ── Stream state ──────────────────────────────────────────────────────────
  messages: Message[];
  activity: AgentEvent[];
  isRunning: boolean;
  critiqueDone: boolean;
  error: string | null;
  sessionId: string | null;
  send: (text: string, figmaUrl?: string, image?: File | null) => void;
  stop: () => void;
  /** Resets stream state AND clears figmaUrl. */
  reset: () => void;
  loadSession: (id: string) => void;
  // ── Per-session UI state ───────────────────────────────────────────────────
  figmaUrl: string;
  setFigmaUrl: (url: string) => void;
  // ── Workspace ─────────────────────────────────────────────────────────────
  activeWorkspaceId: string | undefined;
  setActiveWorkspaceId: (id: string | undefined) => void;
}

const AgentContext = createContext<AgentContextValue | null>(null);

export function AgentProvider({ children }: { children: ReactNode }) {
  const [activeWorkspaceId, setActiveWorkspaceId] = useState<string | undefined>(undefined);
  const [figmaUrl, setFigmaUrl] = useState("");

  const stream = useAgentStream({ workspaceId: activeWorkspaceId });

  // Override reset to also clear figmaUrl
  const reset = useCallback(() => {
    stream.reset();
    setFigmaUrl("");
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [stream.reset]);

  return (
    <AgentContext.Provider
      value={{
        ...stream,
        reset,
        figmaUrl,
        setFigmaUrl,
        activeWorkspaceId,
        setActiveWorkspaceId,
      }}
    >
      {children}
    </AgentContext.Provider>
  );
}

export function useAgentContext(): AgentContextValue {
  const ctx = useContext(AgentContext);
  if (!ctx) throw new Error("useAgentContext must be used within AgentProvider");
  return ctx;
}

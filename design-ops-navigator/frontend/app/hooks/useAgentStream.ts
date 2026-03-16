"use client";

import { useState, useCallback, useRef, useEffect } from "react";

// ── Types matching server.py AG-UI events ─────────────────────────────────────

export type EventType =
  | "TEXT_MESSAGE_CONTENT"
  | "TOOL_CALL_START"
  | "TOOL_CALL_END"
  | "STATE_DELTA"
  | "RUN_FINISHED"
  | "RUN_ERROR";

export interface AgentEvent {
  type: EventType;
  agent?: string;
  text?: string;
  tool?: string;
  args?: Record<string, unknown>;
  status?: string;
  key?: string;
  value?: unknown;
  available?: boolean;
  preview?: string;
  session_id?: string;
  error?: string;
}

export interface Message {
  id: string;
  role: "user" | "assistant";
  text: string;
  isStreaming?: boolean;
  imageUrl?: string; // data URL for user-attached images
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  critiqueData?: Record<string, any>; // structured critique JSON from STATE_DELTA
}

export interface StreamState {
  messages: Message[];
  activity: AgentEvent[];
  sessionId: string | null;
  isRunning: boolean;
  critiqueDone: boolean;
  error: string | null;
}

// ── localStorage helpers ───────────────────────────────────────────────────────

import { auth } from "../lib/firebase";
import { onAuthStateChanged } from "firebase/auth";

/** Wait for Firebase to restore auth state, then return the ID token (or null). */
async function getIdToken(): Promise<string | null> {
  return new Promise((resolve) => {
    // If auth is already resolved, currentUser is set immediately
    if (auth.currentUser) {
      auth.currentUser.getIdToken().then(resolve).catch(() => resolve(null));
      return;
    }
    // Otherwise wait for first auth state change (fires once per page load)
    const timeout = setTimeout(() => { unsubscribe(); resolve(null); }, 5000);
    const unsubscribe = onAuthStateChanged(auth, (user) => {
      clearTimeout(timeout);
      unsubscribe();
      if (!user) { resolve(null); return; }
      user.getIdToken().then(resolve).catch(() => resolve(null));
    });
  });
}
import { storageKey } from "../lib/storage";

const SESSIONS_KEY   = () => storageKey("sessions");
const MSGS_PREFIX    = () => storageKey("msgs.");
const WORKSPACES_KEY = () => storageKey("workspaces");
const FIGMA_TOKEN_KEY = () => storageKey("figma_token");

export function getFigmaToken(): string | null {
  try { return localStorage.getItem(FIGMA_TOKEN_KEY()); } catch { return null; }
}
export function saveFigmaToken(token: string): void {
  try { localStorage.setItem(FIGMA_TOKEN_KEY(), token.trim()); } catch {}
}
export function clearFigmaToken(): void {
  try { localStorage.removeItem(FIGMA_TOKEN_KEY()); } catch {}
}

export interface SessionMeta {
  id: string;
  title: string;
  createdAt: string;
  updatedAt: string;
  figmaUrl?: string;      // stored for History page display
  workspaceId?: string;   // optional project association
}

export interface WorkspaceMeta {
  id: string;
  name: string;
  color: "indigo" | "violet" | "emerald" | "amber" | "rose";
  createdAt: string;
}

function saveSessions(sessions: SessionMeta[]) {
  try { localStorage.setItem(SESSIONS_KEY(), JSON.stringify(sessions)); } catch {}
}

export function loadSessions(): SessionMeta[] {
  try { return JSON.parse(localStorage.getItem(SESSIONS_KEY()) ?? "[]"); } catch { return []; }
}

export function loadWorkspaces(): WorkspaceMeta[] {
  try { return JSON.parse(localStorage.getItem(WORKSPACES_KEY()) ?? "[]"); } catch { return []; }
}

export function saveWorkspaces(workspaces: WorkspaceMeta[]): void {
  try { localStorage.setItem(WORKSPACES_KEY(), JSON.stringify(workspaces)); } catch {}
}

export function createWorkspace(name: string): WorkspaceMeta {
  const colors: WorkspaceMeta["color"][] = ["indigo", "violet", "emerald", "amber", "rose"];
  const existing = loadWorkspaces();
  const color = colors[existing.length % colors.length];
  const ws: WorkspaceMeta = { id: crypto.randomUUID(), name, color, createdAt: new Date().toISOString() };
  saveWorkspaces([...existing, ws]);
  return ws;
}

export function deleteWorkspace(id: string): void {
  saveWorkspaces(loadWorkspaces().filter(w => w.id !== id));
}

function saveMessages(sessionId: string, messages: Message[]) {
  try {
    localStorage.setItem(MSGS_PREFIX() + sessionId, JSON.stringify(messages));
  } catch {}
}

export function loadMessages(sessionId: string): Message[] {
  try {
    return JSON.parse(localStorage.getItem(MSGS_PREFIX() + sessionId) ?? "[]");
  } catch { return []; }
}

function upsertSessionMeta(
  sessionId: string,
  firstMessage: string,
  figmaUrl?: string,
  workspaceId?: string,
) {
  const sessions = loadSessions();
  const now = new Date().toISOString();
  const existing = sessions.find(s => s.id === sessionId);
  if (existing) {
    existing.updatedAt = now;
    if (figmaUrl) existing.figmaUrl = figmaUrl;
    if (workspaceId) existing.workspaceId = workspaceId;
    saveSessions(sessions);
  } else {
    sessions.unshift({
      id: sessionId,
      title: firstMessage.slice(0, 60),
      createdAt: now,
      updatedAt: now,
      figmaUrl: figmaUrl || undefined,
      workspaceId: workspaceId || undefined,
    });
    saveSessions(sessions.slice(0, 50)); // keep last 50 sessions
  }
}

// ── image → base64 ─────────────────────────────────────────────────────────────

async function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const result = reader.result as string;
      // Strip data URL prefix: "data:image/png;base64,<actual-base64>"
      resolve(result.split(",")[1]);
    };
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}

// ── Hook ──────────────────────────────────────────────────────────────────────

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";

interface UseAgentStreamOptions {
  initialSessionId?: string;
  initialMessages?: Message[];
  workspaceId?: string;
}

export function useAgentStream({
  initialSessionId,
  initialMessages = [],
  workspaceId,
}: UseAgentStreamOptions = {}) {
  const [state, setState] = useState<StreamState>({
    messages: initialMessages,
    activity: [],
    sessionId: initialSessionId ?? null,
    isRunning: false,
    critiqueDone: false,
    error: null,
  });

  const abortRef = useRef<AbortController | null>(null);
  const assistantMsgIdRef = useRef<string | null>(null);

  // Abort any in-flight SSE stream when the component unmounts
  useEffect(() => {
    return () => { abortRef.current?.abort(); };
  }, []);

  // Persist messages to localStorage whenever they change
  useEffect(() => {
    if (state.sessionId && state.messages.length > 0 && !state.isRunning) {
      // strip imageUrl before saving to keep storage lean
      const saveable = state.messages.map(m => ({ ...m, imageUrl: undefined }));
      saveMessages(state.sessionId, saveable);
    }
  }, [state.messages, state.sessionId, state.isRunning]);

  const send = useCallback(async (
    userText: string,
    figmaUrl?: string,
    image?: File | null,
  ) => {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    const sessionId = state.sessionId ?? crypto.randomUUID();
    // Strip [Project context — ...]\n\n prefix from chat display — it's already sent to the API
    const displayText = userText.replace(/^\[Project context[^\]]*\]\n\n/, "");
    const userMsg: Message = {
      id: crypto.randomUUID(),
      role: "user",
      text: displayText,
      imageUrl: image ? URL.createObjectURL(image) : undefined,
    };
    const assistantMsgId = crypto.randomUUID();
    assistantMsgIdRef.current = assistantMsgId;

    setState(prev => ({
      ...prev,
      sessionId,
      messages: [...prev.messages, userMsg, { id: assistantMsgId, role: "assistant", text: "", isStreaming: true }],
      activity: [],
      isRunning: true,
      critiqueDone: false,
      error: null,
    }));

    // Track in localStorage
    upsertSessionMeta(sessionId, userText, figmaUrl, workspaceId);

    // Guard: reject images over 10 MB before encoding
    if (image && image.size > 10 * 1024 * 1024) {
      setState(prev => ({
        ...prev,
        isRunning: false,
        error: "Image too large — maximum 10 MB",
        messages: prev.messages.map(m =>
          m.id === assistantMsgId ? { ...m, isStreaming: false } : m
        ),
      }));
      return;
    }

    try {
      // Convert image to base64 if provided
      let imageBase64: string | undefined;
      let imageMimeType: string | undefined;
      if (image) {
        imageBase64 = await fileToBase64(image);
        imageMimeType = image.type;
      }

      const idToken = await getIdToken();
      const authHeader: Record<string, string> = idToken ? { Authorization: `Bearer ${idToken}` } : {};
      const figmaToken = getFigmaToken();
      const figmaHeader: Record<string, string> = figmaToken ? { "X-Figma-Token": figmaToken } : {};

      const resp = await fetch(`${BACKEND_URL}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeader, ...figmaHeader },
        body: JSON.stringify({
          message: userText,
          session_id: sessionId,
          figma_url: figmaUrl || undefined,
          image_base64: imageBase64,
          image_mime_type: imageMimeType,
        }),
        signal: controller.signal,
      });

      // Capture session_id from response header (server may assign one)
      const serverSessionId = resp.headers.get("X-Session-Id");
      if (serverSessionId && serverSessionId !== sessionId) {
        setState(prev => ({ ...prev, sessionId: serverSessionId }));
      }

      const reader = resp.body?.getReader();
      if (!reader) throw new Error("No response body");

      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() ?? "";

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          const raw = line.slice(6).trim();
          if (!raw) continue;

          let event: AgentEvent;
          try { event = JSON.parse(raw); }
          catch { continue; }

          handleEvent(event, assistantMsgId);
        }
      }
    } catch (err: unknown) {
      if (err instanceof Error && err.name === "AbortError") return;
      const msg = err instanceof Error ? err.message : "Connection failed";
      setState(prev => ({
        ...prev,
        isRunning: false,
        error: msg,
        messages: prev.messages.map(m =>
          m.id === assistantMsgIdRef.current ? { ...m, isStreaming: false } : m
        ),
      }));
    }
  }, [state.sessionId]);

  const handleEvent = useCallback((event: AgentEvent, assistantMsgId: string) => {
    setState(prev => {
      const next = { ...prev };

      if (event.type === "TEXT_MESSAGE_CONTENT" && event.text) {
        next.messages = prev.messages.map(m =>
          m.id === assistantMsgId
            ? { ...m, text: m.text + event.text }
            : m
        );
      }

      if (event.type === "TOOL_CALL_START" || event.type === "TOOL_CALL_END" || event.type === "STATE_DELTA") {
        next.activity = [...prev.activity, { ...event, id: crypto.randomUUID() } as AgentEvent];
        if (event.type === "STATE_DELTA" && event.key === "critique_report") {
          next.critiqueDone = true;
          // Capture full JSON for structured card rendering
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          let critiqueValue: Record<string, any> | null = null;
          if (event.value && typeof event.value === "object") {
            critiqueValue = event.value as Record<string, any>;
          } else if (typeof event.value === "string") {
            // Fallback: server sent a raw/fenced string — try to extract JSON
            const raw = (event.value as string).trim();
            const stripped = raw.replace(/^```(?:json)?\s*/i, "").replace(/\s*```$/, "").trim();
            try { critiqueValue = JSON.parse(stripped); } catch {
              try { critiqueValue = JSON.parse(raw); } catch { /* give up */ }
            }
          }
          if (critiqueValue) {
            next.messages = prev.messages.map(m =>
              m.id === assistantMsgId
                ? { ...m, critiqueData: critiqueValue }
                : m
            );
          }
        }
      }

      if (event.type === "RUN_FINISHED") {
        next.isRunning = false;
        next.messages = prev.messages.map(m =>
          m.id === assistantMsgId ? { ...m, isStreaming: false } : m
        );
      }

      if (event.type === "RUN_ERROR") {
        next.isRunning = false;
        next.error = event.error ?? "Agent error";
        next.messages = prev.messages.map(m =>
          m.id === assistantMsgId ? { ...m, isStreaming: false } : m
        );
      }

      return next;
    });
  }, []);

  const stop = useCallback(() => {
    abortRef.current?.abort();
    setState(prev => ({
      ...prev,
      isRunning: false,
      messages: prev.messages.map(m => m.isStreaming ? { ...m, isStreaming: false } : m),
    }));
  }, []);

  const reset = useCallback(() => {
    abortRef.current?.abort();
    setState({ messages: [], activity: [], sessionId: null, isRunning: false, critiqueDone: false, error: null });
  }, []);

  const loadSession = useCallback((sessionId: string) => {
    const messages = loadMessages(sessionId);
    setState({ messages, activity: [], sessionId, isRunning: false, critiqueDone: false, error: null });
  }, []);

  return { ...state, send, stop, reset, loadSession };
}

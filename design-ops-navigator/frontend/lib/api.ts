import { auth } from "@/app/lib/firebase";

const BASE = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";

async function authHeader(): Promise<Record<string, string>> {
  const idToken = await auth.currentUser?.getIdToken().catch(() => null);
  return idToken ? { Authorization: `Bearer ${idToken}` } : {};
}

export interface SessionMeta {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  message_count: number;
}

export async function listServerSessions(): Promise<SessionMeta[]> {
  const res = await fetch(`${BASE}/api/sessions`, { headers: await authHeader() });
  if (!res.ok) return [];
  const data = await res.json();
  return data.sessions ?? [];
}

export interface KnowledgeSource {
  source_file: string;
  source_name: string;
  category: string;
  content_type: string;
  chunk_count: number;
  ingested_at: string;
}

export interface Tier1Source {
  source_name: string;
  category: string;
  description: string;
}

export interface SourcesResponse {
  tier1: Tier1Source[];
  tier2: KnowledgeSource[];
}

export interface UploadResult {
  status: string;
  chunks_written: number;
  source_name: string;
  category: string;
  filename: string;
  error?: string;
}

export async function listSources(): Promise<SourcesResponse> {
  const res = await fetch(`${BASE}/api/knowledge/sources`, { headers: await authHeader() });
  if (!res.ok) throw new Error(`Failed to list sources: ${res.status}`);
  return res.json();
}

export async function uploadDocument(
  file: File,
  sourceName: string,
  category: string,
): Promise<UploadResult> {
  const form = new FormData();
  form.append("file", file);
  if (sourceName) form.append("source_name", sourceName);
  if (category) form.append("category", category);

  const res = await fetch(`${BASE}/api/knowledge/upload`, {
    method: "POST",
    headers: await authHeader(),
    body: form,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail ?? `Upload failed: ${res.status}`);
  }
  return res.json();
}

export interface FetchUrlResult {
  status: string;
  chunks_written: number;
  source_name: string;
  category: string;
  url: string;
  content_length: number;
  error?: string;
}

export async function fetchUrlKnowledge(
  url: string,
  sourceName: string,
  category: string,
): Promise<FetchUrlResult> {
  const res = await fetch(`${BASE}/api/knowledge/fetch-url`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...(await authHeader()) },
    body: JSON.stringify({ url, source_name: sourceName, category }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail ?? `Failed to fetch URL: ${res.status}`);
  }
  return res.json();
}

export async function deleteSource(sourceFile: string): Promise<void> {
  const res = await fetch(`${BASE}/api/knowledge/sources/${encodeURIComponent(sourceFile)}`, {
    method: "DELETE",
    headers: await authHeader(),
  });
  if (!res.ok) throw new Error(`Delete failed: ${res.status}`);
}

// ── Issue feedback ─────────────────────────────────────────────────────────────

export interface IssueFeedback {
  session_id: string;
  issue_index: number;
  element: string;
  severity: string;
  rule_citation: string;
  status: string;          // "fixed" | "in_progress" | "wont_fix" | "open"
  time_to_action_ms?: number;
  workspace_id?: string;
}

/** Fire-and-forget — never throws, never blocks the UI. */
export async function postIssueFeedback(feedback: IssueFeedback): Promise<void> {
  try {
    await fetch(`${BASE}/api/feedback`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...(await authHeader()) },
      body: JSON.stringify(feedback),
    });
  } catch {
    // Intentionally silent — feedback is best-effort
  }
}

// ── Auto-eval quality scores ───────────────────────────────────────────────────

export interface EvalScores {
  sessions: Array<{
    session_id: string;
    scores: Record<string, number>;
    timestamp: string;
  }>;
  averages: Record<string, number>;
  count: number;
}

export async function getEvalScores(): Promise<EvalScores> {
  const res = await fetch(`${BASE}/api/eval-scores`, { headers: await authHeader() });
  if (!res.ok) throw new Error(`Failed to fetch eval scores: ${res.status}`);
  return res.json();
}

// ── Figma comment export ───────────────────────────────────────────────────────

export interface FigmaExportResult {
  posted: number;
  failed: number;
  total: number;
  comments: Array<{ message: string; status: "ok" | "error"; error?: string }>;
}

export async function exportToFigmaComments(
  sessionId: string,
  figmaUrl: string,
  critiqueReport: Record<string, unknown>,
): Promise<FigmaExportResult> {
  const res = await fetch(`${BASE}/api/sessions/${sessionId}/export-figma-comments`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...(await authHeader()) },
    body: JSON.stringify({ figma_url: figmaUrl, critique_report: critiqueReport }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail ?? `Export failed: ${res.status}`);
  }
  return res.json();
}

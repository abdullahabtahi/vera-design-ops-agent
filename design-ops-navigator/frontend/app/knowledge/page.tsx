"use client";

import { useCallback, useEffect, useState } from "react";
import { Link, Loader2, RefreshCw } from "lucide-react";
import { fetchUrlKnowledge, listSources, SourcesResponse } from "../../lib/api";
import { UploadZone } from "../components/knowledge/UploadZone";
import { Tier1List, Tier2List } from "../components/knowledge/SourceList";

const CATEGORY_OPTIONS = [
  "Web Resource",
  "Design System",
  "Accessibility",
  "Usability",
  "Team Docs",
];

function UrlIngestForm({ onIngested }: { onIngested: () => void }) {
  const [url, setUrl] = useState("");
  const [sourceName, setSourceName] = useState("");
  const [category, setCategory] = useState("Web Resource");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<{ ok: boolean; message: string } | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!url.trim()) return;
    setLoading(true);
    setResult(null);
    try {
      const res = await fetchUrlKnowledge(url.trim(), sourceName.trim(), category);
      setResult({ ok: true, message: `Ingested ${res.chunks_written} sections from "${res.source_name}"` });
      setUrl("");
      setSourceName("");
      onIngested();
    } catch (err) {
      setResult({ ok: false, message: err instanceof Error ? err.message : "Ingestion failed" });
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="rounded-lg border border-zinc-800 bg-zinc-900 p-4 space-y-3">
      <div className="flex gap-2">
        <div className="relative flex-1">
          <Link className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-zinc-500" />
          <input
            type="url"
            placeholder="https://developer.apple.com/design/human-interface-guidelines"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            required
            className="w-full bg-zinc-800 border border-zinc-700 rounded-md pl-8 pr-3 py-2 text-sm text-zinc-200 placeholder:text-zinc-600 focus:outline-none focus:border-zinc-500"
          />
        </div>
        <button
          type="submit"
          disabled={loading || !url.trim()}
          className="flex items-center gap-1.5 px-3 py-2 rounded-md bg-zinc-700 hover:bg-zinc-600 text-sm text-zinc-200 disabled:opacity-40 transition-colors shrink-0"
        >
          {loading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : null}
          {loading ? "Fetching…" : "Ingest URL"}
        </button>
      </div>

      <div className="flex gap-2">
        <input
          type="text"
          placeholder="Source name (e.g. Apple HIG)"
          value={sourceName}
          onChange={(e) => setSourceName(e.target.value)}
          className="flex-1 bg-zinc-800 border border-zinc-700 rounded-md px-3 py-1.5 text-sm text-zinc-200 placeholder:text-zinc-600 focus:outline-none focus:border-zinc-500"
        />
        <select
          value={category}
          onChange={(e) => setCategory(e.target.value)}
          className="bg-zinc-800 border border-zinc-700 rounded-md px-2 py-1.5 text-sm text-zinc-200 focus:outline-none focus:border-zinc-500"
        >
          {CATEGORY_OPTIONS.map((c) => (
            <option key={c} value={c}>{c}</option>
          ))}
        </select>
      </div>

      {result && (
        <p className={`text-xs ${result.ok ? "text-emerald-400" : "text-red-400"}`}>
          {result.message}
        </p>
      )}
    </form>
  );
}

export default function KnowledgePage() {
  const [data, setData] = useState<SourcesResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setData(await listSources());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load sources");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const tier2Count = data?.tier2.length ?? 0;
  const tier1Count = data?.tier1.length ?? 0;

  return (
    <div className="h-full overflow-y-auto bg-zinc-950">
      <div className="max-w-3xl mx-auto px-6 py-8 space-y-8">

        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-lg font-semibold text-zinc-100">Knowledge Base</h1>
            <p className="text-sm text-zinc-500 mt-0.5">
              {loading ? "Loading…" : `${tier1Count} built-in · ${tier2Count} team-uploaded`}
            </p>
          </div>
          <button
            onClick={load}
            disabled={loading}
            className="flex items-center gap-1.5 text-xs text-zinc-500 hover:text-zinc-300 transition-colors disabled:opacity-40"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} />
            Refresh
          </button>
        </div>

        {error && (
          <div className="rounded-lg border border-red-900 bg-red-950/40 px-4 py-3">
            <p className="text-sm text-red-400">{error}</p>
          </div>
        )}

        {/* URL ingest */}
        <section>
          <h2 className="text-sm font-semibold text-zinc-300 mb-1">Add from URL</h2>
          <p className="text-xs text-zinc-600 mb-3">
            Paste any public design doc, guidelines page, or article — fetched via Jina Reader
          </p>
          <UrlIngestForm onIngested={load} />
        </section>

        {/* File upload */}
        <section>
          <h2 className="text-sm font-semibold text-zinc-300 mb-3">Upload Team Document</h2>
          <UploadZone onUploaded={load} />
        </section>

        {/* Tier 2 */}
        <section>
          <h2 className="text-sm font-semibold text-zinc-300 mb-1">
            Team Documents
            <span className="ml-2 text-zinc-600 font-normal">Tier 2</span>
          </h2>
          <p className="text-xs text-zinc-600 mb-3">
            Embedded with gemini-embedding-2-preview · searched alongside Tier 1 on every critique
          </p>
          {loading ? (
            <div className="space-y-1">
              {[...Array(3)].map((_, i) => (
                <div key={i} className="h-12 rounded-lg bg-zinc-900 animate-pulse" />
              ))}
            </div>
          ) : (
            <Tier2List sources={data?.tier2 ?? []} onDeleted={load} />
          )}
        </section>

        {/* Tier 1 */}
        <section>
          <h2 className="text-sm font-semibold text-zinc-300 mb-1">
            Built-in UX Rules
            <span className="ml-2 text-zinc-600 font-normal">Tier 1 · read-only</span>
          </h2>
          <p className="text-xs text-zinc-600 mb-3">
            Pre-loaded · embedded with gemini-embedding-001 · always searched
          </p>
          {loading ? (
            <div className="space-y-1">
              {[...Array(5)].map((_, i) => (
                <div key={i} className="h-12 rounded-lg bg-zinc-900 animate-pulse" />
              ))}
            </div>
          ) : (
            <Tier1List sources={data?.tier1 ?? []} />
          )}
        </section>

      </div>
    </div>
  );
}

"use client";

import { Trash2, Lock, FileText, Image } from "lucide-react";
import { KnowledgeSource, Tier1Source, deleteSource } from "../../../lib/api";

interface Tier1ListProps {
  sources: Tier1Source[];
}

export function Tier1List({ sources }: Tier1ListProps) {
  return (
    <div className="space-y-1">
      {sources.map(s => (
        <div key={s.source_name} className="flex items-center justify-between rounded-lg px-3 py-2.5 bg-zinc-900/50 border border-zinc-800">
          <div className="min-w-0">
            <p className="text-sm font-medium text-zinc-200 truncate">{s.source_name}</p>
            <p className="text-xs text-zinc-500 truncate">{s.description}</p>
          </div>
          <div className="flex items-center gap-2 shrink-0 ml-3">
            <span className="rounded bg-zinc-800 px-1.5 py-0.5 text-xs text-zinc-400">{s.category}</span>
            <Lock className="h-3.5 w-3.5 text-zinc-600" />
          </div>
        </div>
      ))}
    </div>
  );
}

interface Tier2ListProps {
  sources: KnowledgeSource[];
  onDeleted: () => void;
}

export function Tier2List({ sources, onDeleted }: Tier2ListProps) {
  async function handleDelete(sourceFile: string) {
    if (!confirm(`Delete "${sourceFile}" from the knowledge base?`)) return;
    try {
      await deleteSource(sourceFile);
      onDeleted();
    } catch (err) {
      alert(err instanceof Error ? err.message : "Delete failed");
    }
  }

  if (sources.length === 0) {
    return (
      <p className="text-sm text-zinc-600 py-4 text-center">
        No documents uploaded yet. Drop a PDF or image above.
      </p>
    );
  }

  return (
    <div className="space-y-1">
      {sources.map(s => {
        const isImage = s.content_type === "image";
        return (
          <div key={s.source_file} className="flex items-center justify-between rounded-lg px-3 py-2.5 bg-zinc-900/50 border border-zinc-800 group">
            <div className="flex items-center gap-2.5 min-w-0">
              {isImage
                ? <Image className="h-4 w-4 shrink-0 text-violet-400" />
                : <FileText className="h-4 w-4 shrink-0 text-blue-400" />
              }
              <div className="min-w-0">
                <p className="text-sm font-medium text-zinc-200 truncate">{s.source_name}</p>
                <p className="text-xs text-zinc-500 truncate">{s.source_file} · {s.chunk_count} chunk{s.chunk_count !== 1 ? "s" : ""}</p>
              </div>
            </div>
            <div className="flex items-center gap-2 shrink-0 ml-3">
              <span className="rounded bg-zinc-800 px-1.5 py-0.5 text-xs text-zinc-400">{s.category}</span>
              <button
                onClick={() => handleDelete(s.source_file)}
                className="opacity-0 group-hover:opacity-100 transition-opacity p-1 rounded hover:bg-red-950/60 text-zinc-500 hover:text-red-400"
                title="Delete source"
              >
                <Trash2 className="h-3.5 w-3.5" />
              </button>
            </div>
          </div>
        );
      })}
    </div>
  );
}

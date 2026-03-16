"use client";

import { useRef, useState, DragEvent, ChangeEvent } from "react";
import { Upload, FileText, Image } from "lucide-react";
import { uploadDocument } from "../../../lib/api";

interface UploadZoneProps {
  onUploaded: () => void;
}

const ACCEPTED = ".pdf,.png,.jpg,.jpeg,.webp,.gif";
const MAX_MB = 20;

export function UploadZone({ onUploaded }: UploadZoneProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [sourceName, setSourceName] = useState("");
  const [category, setCategory] = useState("Team Docs");
  const [result, setResult] = useState<{ ok: boolean; message: string } | null>(null);

  async function handleFiles(files: FileList | null) {
    if (!files || files.length === 0) return;
    const file = files[0];

    if (file.size > MAX_MB * 1024 * 1024) {
      setResult({ ok: false, message: `File too large. Max ${MAX_MB} MB.` });
      return;
    }

    setUploading(true);
    setResult(null);
    try {
      const res = await uploadDocument(file, sourceName, category);
      setResult({ ok: true, message: `Uploaded "${res.source_name}" — ${res.chunks_written} chunks indexed.` });
      setSourceName("");
      onUploaded();
    } catch (err) {
      setResult({ ok: false, message: err instanceof Error ? err.message : "Upload failed" });
    } finally {
      setUploading(false);
    }
  }

  function onDrop(e: DragEvent) {
    e.preventDefault();
    setDragging(false);
    handleFiles(e.dataTransfer.files);
  }

  function onChange(e: ChangeEvent<HTMLInputElement>) {
    handleFiles(e.target.files);
    e.target.value = "";
  }

  return (
    <div className="space-y-3">
      {/* Metadata fields */}
      <div className="flex gap-2">
        <input
          value={sourceName}
          onChange={e => setSourceName(e.target.value)}
          placeholder="Source name (optional — auto from filename)"
          className="flex-1 rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2 text-sm text-zinc-200 placeholder-zinc-600 focus:border-indigo-500 focus:outline-none"
        />
        <select
          value={category}
          onChange={e => setCategory(e.target.value)}
          className="rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2 text-sm text-zinc-200 focus:border-indigo-500 focus:outline-none"
        >
          {["Team Docs", "Design System", "Brand Guidelines", "Accessibility", "Research"].map(c => (
            <option key={c} value={c}>{c}</option>
          ))}
        </select>
      </div>

      {/* Drop zone */}
      <div
        onClick={() => inputRef.current?.click()}
        onDragOver={e => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        className={`relative flex flex-col items-center justify-center gap-3 rounded-xl border-2 border-dashed px-6 py-10 cursor-pointer transition-colors ${
          dragging
            ? "border-indigo-500 bg-indigo-950/20"
            : "border-zinc-700 hover:border-zinc-500 bg-zinc-900/40"
        } ${uploading ? "pointer-events-none opacity-60" : ""}`}
      >
        <input
          ref={inputRef}
          type="file"
          accept={ACCEPTED}
          className="hidden"
          onChange={onChange}
        />
        <div className="flex items-center gap-3 text-zinc-500">
          <FileText className="h-6 w-6" />
          <Upload className="h-5 w-5" />
          <Image className="h-6 w-6" />
        </div>
        <div className="text-center">
          <p className="text-sm font-medium text-zinc-300">
            {uploading ? "Uploading & embedding…" : "Drop file or click to upload"}
          </p>
          <p className="text-xs text-zinc-600 mt-1">PDF, PNG, JPEG, WEBP, GIF · Max {MAX_MB} MB</p>
        </div>
        {uploading && (
          <div className="absolute inset-x-0 bottom-0 h-0.5 rounded-full overflow-hidden">
            <div className="h-full bg-indigo-500 animate-pulse w-full" />
          </div>
        )}
      </div>

      {/* Result */}
      {result && (
        <p className={`text-sm px-3 py-2 rounded-lg ${result.ok ? "bg-emerald-950/40 text-emerald-400 border border-emerald-900" : "bg-red-950/40 text-red-400 border border-red-900"}`}>
          {result.message}
        </p>
      )}
    </div>
  );
}

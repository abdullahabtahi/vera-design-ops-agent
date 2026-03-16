"use client";

import React, { useState, useRef, useEffect, ClipboardEvent, DragEvent } from "react";
import { Paperclip, X, Image as ImageIcon, Accessibility, Eye, LayoutTemplate, Brain } from "lucide-react";
import { Message } from "../hooks/useAgentStream";
import { CritiqueReport } from "./CritiqueReport";

interface ChatWindowProps {
  messages: Message[];
  isRunning: boolean;
  onSend: (text: string, image?: File | null) => void;
  initialInput?: string;
  figmaUrl?: string;
  sessionId?: string;
}

function MessageBubble({ msg, figmaUrl, sessionId }: { msg: Message; figmaUrl?: string; sessionId?: string }) {
  const isUser = msg.role === "user";

  if (isUser) {
    return (
      <div className="flex justify-end">
        <div className="max-w-[80%] space-y-2">
          {msg.imageUrl && (
            <div className="flex justify-end">
              <img
                src={msg.imageUrl}
                alt="Attached screenshot"
                className="max-h-48 rounded-xl border border-white/[0.08] object-contain"
              />
            </div>
          )}
          {msg.text && (
            <div className="rounded-2xl rounded-tr-sm bg-indigo-600 px-4 py-2.5">
              <p className="text-sm text-white">{msg.text}</p>
            </div>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="flex justify-start">
      <div className="max-w-[92%]">
        <div className="flex items-center gap-1.5 mb-1.5">
          <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
          <span className="text-xs text-zinc-500">Design Ops Navigator</span>
        </div>
        {msg.critiqueData && !msg.isStreaming ? (
          <CritiqueReport data={msg.critiqueData} figmaUrl={figmaUrl} sessionId={sessionId} />
        ) : (
          <div className="rounded-2xl rounded-tl-sm bg-zinc-900 border border-white/[0.06] px-4 py-2.5">
            <p className="text-sm text-zinc-100 whitespace-pre-wrap leading-relaxed">{msg.text}</p>
            {msg.isStreaming && (
              <span className="inline-block w-1 h-3.5 bg-zinc-400 animate-pulse ml-0.5 align-middle" />
            )}
          </div>
        )}
      </div>
    </div>
  );
}

const CAPABILITIES = [
  { icon: Accessibility, label: "WCAG 2.2", desc: "Contrast, focus, alt-text" },
  { icon: Eye, label: "Gestalt", desc: "Visual hierarchy & grouping" },
  { icon: LayoutTemplate, label: "Nielsen", desc: "10 usability heuristics" },
  { icon: Brain, label: "Cognitive", desc: "Fitts, Hick, Miller laws" },
];

const SUGGESTIONS = [
  "What accessibility issues does this design have?",
  "Check the contrast ratios on this frame",
  "Does this layout follow Gestalt principles?",
  "What are the cognitive load concerns here?",
  "Explain WCAG 1.4.3 contrast requirements",
];

const ACCEPTED_IMAGE_TYPES = ["image/png", "image/jpeg", "image/webp", "image/gif"];

export function ChatWindow({ messages, isRunning, onSend, initialInput, figmaUrl, sessionId }: ChatWindowProps) {
  const [input, setInput] = useState(initialInput ?? "");

  // Sync input when initialInput changes (e.g. playbook navigation)
  useEffect(() => {
    if (initialInput !== undefined) setInput(initialInput);
  }, [initialInput]);
  const [attachedImage, setAttachedImage] = useState<File | null>(null);
  const [imagePreview, setImagePreview] = useState<string | null>(null);
  const [draggingOver, setDraggingOver] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  function attachFile(file: File) {
    if (!ACCEPTED_IMAGE_TYPES.includes(file.type)) return;
    setAttachedImage(file);
    setImagePreview(URL.createObjectURL(file));
  }

  function clearImage() {
    setAttachedImage(null);
    if (imagePreview) URL.revokeObjectURL(imagePreview);
    setImagePreview(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
  }

  function handlePaste(e: ClipboardEvent<HTMLTextAreaElement>) {
    const items = e.clipboardData.items;
    for (let i = 0; i < items.length; i++) {
      if (items[i].type.startsWith("image/")) {
        const file = items[i].getAsFile();
        if (file) { attachFile(file); break; }
      }
    }
  }

  function handleDragOver(e: DragEvent) {
    e.preventDefault();
    setDraggingOver(true);
  }

  function handleDragLeave() { setDraggingOver(false); }

  function handleDrop(e: DragEvent) {
    e.preventDefault();
    setDraggingOver(false);
    const file = e.dataTransfer.files[0];
    if (file) attachFile(file);
  }

  function handleSubmit(e: React.SyntheticEvent) {
    e.preventDefault();
    const text = input.trim();
    if ((!text && !attachedImage) || isRunning) return;
    onSend(text, attachedImage);
    setInput("");
    clearImage();
  }

  // Auto-resize textarea
  useEffect(() => {
    const ta = textareaRef.current;
    if (!ta) return;
    ta.style.height = "auto";
    ta.style.height = `${Math.min(ta.scrollHeight, 160)}px`;
  }, [input]);

  return (
    <div
      className={`flex flex-col h-full transition-colors ${draggingOver ? "bg-indigo-950/10" : ""}`}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
    >
      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4 min-h-0">
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full gap-7 px-4 py-8">
            {/* Hero */}
            <div className="text-center max-w-xs">
              <h2 className="text-base font-semibold text-zinc-200">Evidence-based UX critique</h2>
              <p className="text-sm text-zinc-600 mt-1.5 leading-relaxed">
                Paste a screenshot or add a Figma URL above — get grounded feedback with rule citations and actionable fixes.
              </p>
            </div>

            {/* Capability chips */}
            <div className="grid grid-cols-2 gap-2 w-full max-w-sm">
              {CAPABILITIES.map(({ icon: Icon, label, desc }) => (
                <div
                  key={label}
                  className="flex items-center gap-2.5 rounded-lg border border-white/[0.06] bg-white/[0.02] px-3 py-2.5"
                >
                  <Icon className="h-3.5 w-3.5 shrink-0 text-indigo-400" />
                  <div className="min-w-0">
                    <p className="text-xs font-medium text-zinc-300 leading-tight">{label}</p>
                    <p className="text-[11px] text-zinc-600 truncate">{desc}</p>
                  </div>
                </div>
              ))}
            </div>

            {/* Suggestion chips */}
            <div className="w-full max-w-sm">
              <p className="text-[11px] text-zinc-700 uppercase tracking-wider font-medium mb-2 text-center">Try asking</p>
              <div className="flex flex-wrap gap-1.5 justify-center">
                {SUGGESTIONS.map(s => (
                  <button
                    key={s}
                    onClick={() => onSend(s)}
                    className="rounded-full border border-white/[0.08] px-3 py-1.5 text-xs text-zinc-500 hover:border-indigo-500/40 hover:text-zinc-300 hover:bg-indigo-950/20 transition-colors text-left"
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}
        {messages.map(msg => <MessageBubble key={msg.id} msg={msg} figmaUrl={figmaUrl} sessionId={sessionId} />)}
        <div ref={bottomRef} />
      </div>

      {/* Input area */}
      <div className="border-t border-white/[0.06] px-4 py-3">
        {/* Image preview */}
        {imagePreview && (
          <div className="relative inline-block mb-2">
            <img
              src={imagePreview}
              alt="Attached"
              className="h-20 w-auto rounded-lg border border-white/[0.08] object-cover"
            />
            <button
              onClick={clearImage}
              className="absolute -top-1.5 -right-1.5 flex h-5 w-5 items-center justify-center rounded-full bg-zinc-800 border border-white/[0.1] text-zinc-400 hover:text-zinc-100 transition-colors"
            >
              <X className="h-3 w-3" />
            </button>
          </div>
        )}

        {/* Drop hint when dragging */}
        {draggingOver && (
          <div className="flex items-center gap-2 mb-2 text-xs text-indigo-400">
            <ImageIcon className="h-3.5 w-3.5" />
            Drop image to attach
          </div>
        )}

        <form onSubmit={handleSubmit} className="flex items-end gap-2">
          {/* Hidden file input */}
          <input
            ref={fileInputRef}
            type="file"
            accept="image/*"
            className="hidden"
            onChange={e => { const f = e.target.files?.[0]; if (f) attachFile(f); }}
          />

          {/* Attach button */}
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            disabled={isRunning}
            title="Attach screenshot"
            className={`shrink-0 flex h-9 w-9 items-center justify-center rounded-xl border transition-colors ${
              attachedImage
                ? "border-indigo-500/60 bg-indigo-950/30 text-indigo-400"
                : "border-white/[0.08] bg-white/[0.03] text-zinc-500 hover:text-zinc-300 hover:border-white/[0.16]"
            } disabled:opacity-40`}
          >
            <Paperclip className="h-4 w-4" />
          </button>

          {/* Text input */}
          <textarea
            ref={textareaRef}
            rows={1}
            value={input}
            onChange={e => setInput(e.target.value)}
            onPaste={handlePaste}
            onKeyDown={e => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                handleSubmit(e as unknown as React.SyntheticEvent);
              }
            }}
            placeholder={
              isRunning
                ? "Agents are working…"
                : attachedImage
                ? "Ask about this screenshot… (or just press Send)"
                : "Ask about accessibility, layout, Gestalt… or paste a screenshot"
            }
            disabled={isRunning}
            className="flex-1 resize-none rounded-xl border border-white/[0.08] bg-white/[0.03] px-4 py-2.5 text-sm text-zinc-100 placeholder-zinc-600 focus:border-indigo-500/50 focus:outline-none disabled:opacity-50 transition-colors leading-relaxed"
          />

          {/* Send button */}
          <button
            type="submit"
            disabled={isRunning || (!input.trim() && !attachedImage)}
            className="shrink-0 rounded-xl bg-indigo-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            {isRunning ? "…" : "Send"}
          </button>
        </form>
        <p className="mt-1.5 text-[11px] text-zinc-700">
          Paste image with ⌘V · Drag & drop · <span className="text-zinc-600">Shift+Enter for new line</span>
        </p>
      </div>
    </div>
  );
}

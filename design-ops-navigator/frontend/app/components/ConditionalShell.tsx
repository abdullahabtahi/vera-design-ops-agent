"use client";

import { usePathname } from "next/navigation";
import { AppShell } from "./AppShell";
import { Sidebar } from "./Sidebar";
import { AgentProvider } from "../contexts/AgentContext";

export function ConditionalShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  // Public pages get a plain full-screen container (no sidebar, no agent context)
  if (pathname === "/auth") {
    return <div className="min-h-screen bg-zinc-950">{children}</div>;
  }

  // App pages: AgentProvider wraps the whole shell so the stream survives navigation
  return (
    <AgentProvider>
      <AppShell>
        <Sidebar />
        <main className="flex-1 min-w-0 overflow-hidden">{children}</main>
      </AppShell>
    </AgentProvider>
  );
}

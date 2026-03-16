"use client";

import { createContext, useContext, useState, ReactNode } from "react";

interface SidebarCtx {
  collapsed: boolean;
  toggle: () => void;
}

const SidebarContext = createContext<SidebarCtx>({ collapsed: false, toggle: () => {} });

export function useSidebar() {
  return useContext(SidebarContext);
}

export function AppShell({ children }: { children: ReactNode }) {
  const [collapsed, setCollapsed] = useState(false);

  return (
    <SidebarContext.Provider value={{ collapsed, toggle: () => setCollapsed(p => !p) }}>
      <div className="flex h-screen overflow-hidden bg-zinc-950">
        {children}
      </div>
    </SidebarContext.Provider>
  );
}

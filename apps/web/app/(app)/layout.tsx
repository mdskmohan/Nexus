"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { Sidebar } from "@/components/layout/sidebar";
import { Topbar } from "@/components/layout/topbar";
import { Callout } from "@/components/ui/callout";
import { api, ApiError, can, type HumanRequest, type Me } from "@/lib/api";
import { MeContext } from "@/lib/me";

const COLLAPSED_KEY = "nexus.sidebar.collapsed";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [me, setMe] = useState<Me | null>(null);
  const [collapsed, setCollapsed] = useState(false);
  const [waiting, setWaiting] = useState(0);

  useEffect(() => {
    api.get<Me>("/me").then(setMe).catch((e) => {
      if (e instanceof ApiError && e.status === 401) router.replace("/signin");
    });
    try { setCollapsed(localStorage.getItem(COLLAPSED_KEY) === "true"); } catch {}
  }, [router]);

  useEffect(() => {
    if (!me) return;
    const load = () => api.get<HumanRequest[]>("/requests").then((r) => setWaiting(r.length)).catch(() => {});
    load();
    const t = setInterval(load, 15000);
    return () => clearInterval(t);
  }, [me]);

  const toggle = useCallback(() => {
    setCollapsed((prev) => {
      try { localStorage.setItem(COLLAPSED_KEY, String(!prev)); } catch {}
      return !prev;
    });
  }, []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "\\") { e.preventDefault(); toggle(); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [toggle]);

  async function signOut() {
    await api.post("/auth/logout");
    router.replace("/signin");
  }

  if (!me) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="flex items-center gap-2 text-body text-muted-foreground">
          <span className="size-1.5 animate-pulse-dot rounded-full bg-primary" /> Loading…
        </div>
      </div>
    );
  }

  const width = collapsed ? 56 : 232;
  return (
    <MeContext.Provider value={me}>
      <a href="#main" className="skip-link">Skip to content</a>
      <Sidebar me={me} collapsed={collapsed} onToggle={toggle} onSignOut={signOut} waiting={waiting} />
      <Topbar me={me} left={width} onSignOut={signOut} />
      <main id="main" tabIndex={-1} className="min-h-screen pt-14 transition-[margin] duration-200" style={{ marginLeft: width }}>
        <div className="mx-auto w-full max-w-6xl space-y-6 px-6 py-6 animate-fade-in">
          {!me.model_configured && (
            <Callout tone="warning" title="AI is not connected yet.">
              Agents need an AI model.{" "}
              {can(me, "manage_ai")
                ? <Link href="/settings" className="font-medium underline underline-offset-2">Connect one in Settings</Link>
                : "Ask your administrator to connect one."}
            </Callout>
          )}
          {children}
        </div>
      </main>
    </MeContext.Provider>
  );
}

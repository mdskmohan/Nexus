"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api, ApiError, type Me } from "@/lib/api";
import { MeContext } from "@/lib/me";

const NAV = [
  { href: "/", label: "Matters", match: (p: string) => p === "/" || p.startsWith("/matters") || p.startsWith("/tasks") },
  { href: "/safety", label: "Safety & activity", match: (p: string) => p.startsWith("/safety") },
  { href: "/playbooks", label: "Review playbooks", match: (p: string) => p.startsWith("/playbooks") },
  { href: "/settings", label: "Firm settings", match: (p: string) => p.startsWith("/settings") },
];

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const path = usePathname();
  const [me, setMe] = useState<Me | null>(null);

  useEffect(() => {
    api.get<Me>("/me").then(setMe).catch((e) => {
      if (e instanceof ApiError && e.status === 401) router.replace("/signin");
    });
  }, [router]);

  async function signOut() {
    await api.post("/auth/logout");
    router.replace("/signin");
  }

  if (!me) return <div className="empty">Loading…</div>;

  return (
    <MeContext.Provider value={me}>
      <div className="shell">
        <aside className="sidebar">
          <Link href="/" className="brand" style={{ textDecoration: "none", color: "inherit" }}>
            <div className="brand-mark">N</div>
            <span className="brand-name">Nexus</span>
          </Link>
          <nav className="nav">
            {NAV.map((item) => (
              <Link key={item.href} href={item.href} className={item.match(path) ? "active" : ""}>
                {item.label}
              </Link>
            ))}
          </nav>
          <div className="sidebar-foot stack" style={{ gap: 6 }}>
            <div>
              <div style={{ color: "var(--ink)", fontWeight: 600 }}>{me.user.name}</div>
              <div>{me.firm.name} · {me.user.role}</div>
            </div>
            <button className="btn-quiet btn-small" style={{ padding: 0, justifyContent: "flex-start" }} onClick={signOut}>
              Sign out
            </button>
          </div>
        </aside>
        <main className="main">
          {!me.model_configured && (
            <div className="notice notice-warn" style={{ marginBottom: 20 }}>
              <p>
                <strong>AI is not connected yet.</strong> You can add matters and documents, but questions,
                reviews and drafts need an AI model.{" "}
                {me.user.role === "admin"
                  ? <Link href="/settings">Connect one in Firm settings</Link>
                  : "Ask your administrator to connect one in Firm settings."}
              </p>
            </div>
          )}
          {children}
        </main>
      </div>
    </MeContext.Provider>
  );
}

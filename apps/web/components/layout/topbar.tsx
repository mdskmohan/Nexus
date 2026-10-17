"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { useTheme } from "next-themes";
import { Building2, ChevronRight, LogOut, Moon, Settings, Sun } from "lucide-react";
import { Avatar } from "@/components/ui/avatar";
import type { Me } from "@/lib/api";
import { cn } from "@/lib/utils";

const LABELS: Record<string, string> = {
  "/": "Home", "/approvals": "Approvals", "/knowledge": "Knowledge graph", "/connections": "Connections",
  "/settings": "Settings",
};

function Breadcrumb() {
  const path = usePathname();
  const parts = path.split("/").filter(Boolean);
  if (!parts.length) return <span className="font-medium text-foreground">Home</span>;
  let href = "";
  return (
    <nav className="flex items-center gap-1 text-caption">
      {parts.map((p, i) => {
        href += `/${p}`;
        const label = LABELS[href] ?? (p.length > 12 ? `${p.slice(0, 8)}…` : p);
        return (
          <span key={href} className="flex items-center gap-1">
            {i > 0 && <ChevronRight className="size-3 text-muted-foreground/60" />}
            {i === parts.length - 1 ? <span className="font-medium text-foreground">{label}</span>
              : <Link href={href} className="text-muted-foreground hover:text-foreground">{label}</Link>}
          </span>
        );
      })}
    </nav>
  );
}

export function Topbar({ me, left, onSignOut }: { me: Me; left: number; onSignOut: () => void }) {
  const { resolvedTheme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);
  const [menu, setMenu] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => setMounted(true), []);
  useEffect(() => {
    if (!menu) return;
    const close = (e: MouseEvent) => { if (!ref.current?.contains(e.target as Node)) setMenu(false); };
    window.addEventListener("mousedown", close);
    return () => window.removeEventListener("mousedown", close);
  }, [menu]);
  const dark = mounted && resolvedTheme === "dark";

  return (
    <header className="fixed right-0 top-0 z-20 flex h-14 items-center gap-3 border-b border-border bg-background/85 px-4 backdrop-blur transition-[left] duration-200"
      style={{ left }}>
      <div className="flex min-w-0 items-center gap-3">
        <span className="flex items-center gap-2 rounded-md px-2 py-1 text-body font-medium text-foreground">
          <Building2 className="size-4 text-muted-foreground" />
          <span className="max-w-[180px] truncate">{me.workspace.name}</span>
        </span>
        <span aria-hidden className="hidden h-4 w-px bg-border-strong md:inline-block" />
        <div className="hidden min-w-0 md:block"><Breadcrumb /></div>
      </div>

      <div className="ml-auto flex items-center gap-1">
        <button className="inline-flex size-8 items-center justify-center rounded-md text-muted-foreground hover:bg-accent hover:text-foreground"
          title={dark ? "Switch to light mode" : "Switch to dark mode"} aria-label={dark ? "Switch to light mode" : "Switch to dark mode"} onClick={() => setTheme(dark ? "light" : "dark")}>
          {dark ? <Sun className="size-4" /> : <Moon className="size-4" />}
        </button>
        <div ref={ref} className="relative ml-1">
          <button onClick={() => setMenu(!menu)} className="flex h-8 items-center gap-2 rounded-md px-2 hover:bg-accent">
            <Avatar name={me.user.name} className="size-6" />
            <span className="hidden max-w-[140px] truncate text-caption font-medium text-foreground sm:block">{me.user.name}</span>
          </button>
          {menu && (
            <div className="absolute right-0 top-10 z-50 w-60 animate-fade-in rounded-lg border border-border bg-popover p-1 shadow-lg">
              <div className="px-2.5 py-2">
                <p className="truncate text-body font-medium text-foreground">{me.user.name}</p>
                <p className="truncate text-caption text-muted-foreground">{me.user.email}</p>
                <span className="mt-1.5 inline-flex rounded-md bg-primary-soft px-1.5 py-0.5 text-caption font-medium uppercase tracking-wider text-primary">{me.user.role}</span>
              </div>
              <div className="my-1 h-px bg-border" />
              <Link href="/settings" onClick={() => setMenu(false)} className="flex items-center gap-2 rounded-md px-2.5 py-1.5 text-body hover:bg-accent">
                <Settings className="size-3.5" /> Settings
              </Link>
              <button onClick={onSignOut} className={cn("flex w-full items-center gap-2 rounded-md px-2.5 py-1.5 text-body text-danger hover:bg-danger-soft")}>
                <LogOut className="size-3.5" /> Sign out
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}

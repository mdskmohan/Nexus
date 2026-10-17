"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Cable, Inbox, LayoutDashboard, LogOut, Network, PanelLeftClose, PanelLeftOpen, Settings, Workflow,
  type LucideIcon,
} from "lucide-react";
import { Logo } from "@/components/logo";
import { Avatar } from "@/components/ui/avatar";
import { can, type Me, type Permission } from "@/lib/api";
import { cn } from "@/lib/utils";

type NavItem = { href: string; label: string; icon: LucideIcon; soon?: boolean; needs?: Permission[]; badge?: number };

export function Sidebar({ me, collapsed, onToggle, onSignOut, waiting }: {
  me: Me; collapsed: boolean; onToggle: () => void; onSignOut: () => void; waiting: number;
}) {
  const path = usePathname();
  const groups: { group: string | null; items: NavItem[] }[] = [
    { group: null, items: [
      { href: "/", label: "Home", icon: LayoutDashboard },
      { href: "/approvals", label: "Approvals", icon: Inbox, badge: waiting },
    ] },
    { group: "Data", items: [
      { href: "/knowledge", label: "Knowledge graph", icon: Network, needs: ["approve_graph", "build_agents", "manage_connections"] },
      { href: "/connections", label: "Connections", icon: Cable, needs: ["approve_graph", "build_agents", "manage_connections"] },
    ] },
    { group: "Agents", items: [{ href: "/studio", label: "Agent Studio", icon: Workflow, soon: true }] },
    { group: null, items: [{ href: "/settings", label: "Settings", icon: Settings }] },
  ];
  const active = (href: string) => (href === "/" ? path === "/" : path.startsWith(href));

  return (
    <aside aria-label="Primary" className={cn(
      "fixed inset-y-0 left-0 z-30 flex flex-col border-r border-border bg-card transition-[width] duration-200",
      collapsed ? "w-14" : "w-[232px]")}>
      <div className="flex h-14 items-center justify-between border-b border-border px-3">
        <Link href="/" className="min-w-0"><Logo collapsed={collapsed} /></Link>
        {!collapsed && (
          <button onClick={onToggle} title="Collapse sidebar (⌘\)" className="text-muted-foreground transition-colors hover:text-foreground">
            <PanelLeftClose className="size-4" />
          </button>
        )}
      </div>
      {collapsed && (
        <button onClick={onToggle} title="Expand sidebar (⌘\)" className="mx-auto mt-3 text-muted-foreground hover:text-foreground">
          <PanelLeftOpen className="size-4" />
        </button>
      )}

      <nav className="flex-1 space-y-1 overflow-y-auto px-2 py-3">
        {groups.map((section, i) => {
          const items = section.items.filter((it) => !it.needs || it.needs.some((p) => can(me, p)));
          if (!items.length) return null;
          return (
            <div key={i} className={section.group ? "pt-3" : ""}>
              {section.group && !collapsed && (
                <p className="mb-1 px-2 text-caption font-semibold uppercase tracking-widest text-muted-foreground/80">{section.group}</p>
              )}
              {section.group && collapsed && <div className="mx-1 mb-1 h-px bg-border-strong/40" />}
              <ul className="space-y-0.5">
                {items.map((item) => {
                  const Icon = item.icon;
                  const on = active(item.href);
                  const body = (
                    <>
                      {on && !collapsed && <span aria-hidden className="absolute left-0 top-1/2 h-5 w-0.5 -translate-y-1/2 rounded-r-full bg-primary" />}
                      <Icon className="size-4 shrink-0" />
                      {!collapsed && <span className="flex-1 truncate">{item.label}</span>}
                      {!collapsed && item.soon && <span className="rounded bg-muted px-1.5 text-caption text-muted-foreground">Soon</span>}
                      {!collapsed && !!item.badge && <span className="num rounded bg-warning-soft px-1.5 text-caption font-medium text-warning-soft-foreground">{item.badge}</span>}
                      {collapsed && !!item.badge && <span className="absolute right-1.5 top-1.5 size-1.5 rounded-full bg-warning" />}
                      {collapsed && (
                        <span className="absolute left-full z-50 ml-2 hidden whitespace-nowrap rounded-md border border-border bg-popover px-2 py-1 text-caption text-foreground shadow-md group-hover:flex">
                          {item.label}{item.soon ? " (soon)" : ""}
                        </span>
                      )}
                    </>
                  );
                  const cls = cn("group relative flex h-9 items-center gap-2.5 rounded-md text-body transition-colors",
                    collapsed ? "justify-center" : "px-2.5",
                    on ? "bg-primary-soft font-medium text-primary" : "text-muted-foreground hover:bg-muted/60 hover:text-foreground",
                    item.soon && "cursor-default opacity-60 hover:bg-transparent hover:text-muted-foreground");
                  return (
                    <li key={item.href}>
                      {item.soon ? <span className={cls} title="Arrives in M2">{body}</span> : <Link href={item.href} className={cls}>{body}</Link>}
                    </li>
                  );
                })}
              </ul>
            </div>
          );
        })}
      </nav>

      <div className={cn("border-t border-border p-3", collapsed && "flex justify-center")}>
        {collapsed ? <Avatar name={me.user.name} /> : (
          <div className="flex items-center gap-2.5">
            <Avatar name={me.user.name} />
            <div className="min-w-0 flex-1">
              <p className="truncate text-body font-medium text-foreground">{me.user.name}</p>
              <p className="truncate text-caption capitalize text-muted-foreground">{me.user.role}</p>
            </div>
            <button onClick={onSignOut} title="Sign out" className="rounded-md p-1.5 text-muted-foreground hover:bg-accent hover:text-foreground">
              <LogOut className="size-4" />
            </button>
          </div>
        )}
      </div>
    </aside>
  );
}

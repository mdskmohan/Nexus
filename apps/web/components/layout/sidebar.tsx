"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import {
  AlertTriangle,
  Boxes,
  GitBranch,
  LayoutGrid,
  Plug,
  Settings,
  ShieldCheck,
} from "lucide-react"

import { cn } from "@/lib/utils"

interface NavItem {
  href: string
  label: string
  icon: React.ComponentType<{ className?: string }>
  /** Rendered as a count chip; omitted when zero so the chrome stays quiet. */
  badge?: number
}

const PRIMARY: NavItem[] = [
  { href: "/", label: "Overview", icon: LayoutGrid },
  { href: "/pipelines", label: "Pipelines", icon: GitBranch },
  { href: "/incidents", label: "Incidents", icon: AlertTriangle, badge: 2 },
  { href: "/graph", label: "Environment", icon: Boxes },
]

const SECONDARY: NavItem[] = [
  { href: "/connections", label: "Connections", icon: Plug },
  { href: "/policy", label: "Autonomy", icon: ShieldCheck },
  { href: "/settings", label: "Settings", icon: Settings },
]

function NavLink({ item, active }: { item: NavItem; active: boolean }) {
  const Icon = item.icon
  return (
    <Link
      href={item.href}
      aria-current={active ? "page" : undefined}
      className={cn(
        "group flex h-7 items-center gap-2 rounded-md px-2 text-body transition-colors duration-[var(--motion-fast)]",
        active
          ? "bg-accent font-medium text-accent-foreground"
          : "text-muted-foreground hover:bg-accent/60 hover:text-foreground"
      )}
    >
      <Icon className="size-4 shrink-0" />
      <span className="truncate">{item.label}</span>
      {item.badge ? (
        <span className="ml-auto rounded-sm bg-danger-soft px-1.5 text-caption font-medium text-danger-soft-foreground">
          {item.badge}
        </span>
      ) : null}
    </Link>
  )
}

export function Sidebar() {
  const pathname = usePathname()
  const isActive = (href: string) =>
    href === "/" ? pathname === "/" : pathname.startsWith(href)

  return (
    <aside className="flex h-full w-56 shrink-0 flex-col border-r border-border bg-card">
      <div className="flex h-12 items-center gap-2 px-3">
        <div className="grid size-6 place-items-center rounded-md bg-primary text-primary-foreground">
          <span className="text-caption font-bold">N</span>
        </div>
        <span className="text-h2">Nexus</span>
      </div>

      <nav className="flex flex-1 flex-col gap-0.5 px-2" aria-label="Primary">
        {PRIMARY.map((item) => (
          <NavLink key={item.href} item={item} active={isActive(item.href)} />
        ))}

        <div className="mt-auto flex flex-col gap-0.5 pb-2">
          {SECONDARY.map((item) => (
            <NavLink key={item.href} item={item} active={isActive(item.href)} />
          ))}
        </div>
      </nav>

      <div className="border-t border-border p-3">
        <div className="flex items-center gap-2">
          <div className="grid size-6 shrink-0 place-items-center rounded-full bg-muted text-caption font-medium text-muted-foreground">
            AC
          </div>
          <div className="min-w-0">
            <div className="truncate text-caption font-medium">Acme Corp</div>
            <div className="truncate text-caption text-muted-foreground">Production</div>
          </div>
        </div>
      </div>
    </aside>
  )
}

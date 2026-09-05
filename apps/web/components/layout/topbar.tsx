import { Search } from "lucide-react"

import { Button } from "@/components/ui/button"
import { ThemeToggle } from "@/components/layout/theme-toggle"

interface TopbarProps {
  title: string
  description?: string
  /** Page-specific actions, rendered right-aligned. */
  actions?: React.ReactNode
}

export function Topbar({ title, description, actions }: TopbarProps) {
  return (
    <header className="flex h-12 shrink-0 items-center gap-3 border-b border-border px-4">
      <div className="min-w-0">
        <h1 className="truncate text-h2">{title}</h1>
        {description ? (
          <p className="truncate text-caption text-muted-foreground">{description}</p>
        ) : null}
      </div>

      <div className="ml-auto flex items-center gap-2">
        <Button variant="outline" size="sm" className="gap-2 text-muted-foreground">
          <Search className="size-3.5" />
          <span>Search</span>
          <kbd className="ml-1 rounded border border-border bg-muted px-1 font-mono text-caption">
            ⌘K
          </kbd>
        </Button>
        <ThemeToggle />
        {actions}
      </div>
    </header>
  )
}

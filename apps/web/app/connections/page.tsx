"use client"

import * as React from "react"
import { AlertTriangle, Loader2, Plug } from "lucide-react"

import { Topbar } from "@/components/layout/topbar"
import { Card } from "@/components/ui/card"
import { ConnectionForm } from "@/components/connections/connection-form"
import { CATEGORY_LABELS, type Connector, listConnectors } from "@/lib/api"
import { cn } from "@/lib/utils"

export default function ConnectionsPage() {
  const [connectors, setConnectors] = React.useState<Connector[]>([])
  const [selected, setSelected] = React.useState<string | null>(null)
  const [loading, setLoading] = React.useState(true)
  const [error, setError] = React.useState<string | null>(null)

  React.useEffect(() => {
    let cancelled = false
    listConnectors()
      .then((list) => {
        if (cancelled) return
        setConnectors(list)
        setSelected((current) => current ?? list[0]?.id ?? null)
      })
      .catch((e) => !cancelled && setError(e instanceof Error ? e.message : String(e)))
      .finally(() => !cancelled && setLoading(false))
    return () => {
      cancelled = true
    }
  }, [])

  const grouped = React.useMemo(() => {
    const byCategory = new Map<string, Connector[]>()
    for (const c of connectors) {
      const list = byCategory.get(c.category) ?? []
      list.push(c)
      byCategory.set(c.category, list)
    }
    return Array.from(byCategory.entries())
  }, [connectors])

  const active = connectors.find((c) => c.id === selected) ?? null

  return (
    <>
      <Topbar
        title="Connections"
        description="Configure the platforms Nexus should read, build on, and operate"
      />

      <div className="flex-1 overflow-y-auto p-4">
        {loading ? (
          <div className="flex items-center gap-2 text-muted-foreground">
            <Loader2 className="size-4 animate-spin" />
            Loading connectors…
          </div>
        ) : error ? (
          <Card className="flex items-start gap-2 border-danger/40 bg-danger-soft/40 p-3">
            <AlertTriangle className="mt-0.5 size-4 shrink-0 text-danger" />
            <div>
              <div className="font-medium">Could not load connectors</div>
              <p className="mt-0.5 text-caption text-muted-foreground">{error}</p>
              <p className="mt-1.5 text-caption text-muted-foreground">
                Start the API with{" "}
                <span className="font-mono">make api</span> from the repository root.
              </p>
            </div>
          </Card>
        ) : (
          <div className="grid gap-4 lg:grid-cols-[260px_minmax(0,1fr)]">
            <nav className="flex flex-col gap-4" aria-label="Available platforms">
              {grouped.map(([category, items]) => (
                <div key={category}>
                  <h2 className="mb-1.5 px-2 text-caption font-medium uppercase tracking-wide text-muted-foreground">
                    {CATEGORY_LABELS[category] ?? category}
                  </h2>
                  <div className="flex flex-col gap-0.5">
                    {items.map((c) => (
                      <button
                        key={c.id}
                        type="button"
                        onClick={() => setSelected(c.id)}
                        aria-current={c.id === selected ? "true" : undefined}
                        className={cn(
                          "flex items-center gap-2 rounded-md px-2 py-1.5 text-left text-body transition-colors duration-[var(--motion-fast)]",
                          c.id === selected
                            ? "bg-accent font-medium text-accent-foreground"
                            : "text-muted-foreground hover:bg-accent/60 hover:text-foreground"
                        )}
                      >
                        <Plug className="size-3.5 shrink-0" />
                        <span className="min-w-0 flex-1 truncate">{c.name}</span>
                        {!c.verified ? (
                          <span
                            className="size-1.5 shrink-0 rounded-full bg-warning"
                            title="Not yet verified against a real account"
                            aria-label="Not yet verified"
                          />
                        ) : null}
                      </button>
                    ))}
                  </div>
                </div>
              ))}
            </nav>

            <Card className="p-4">
              {active ? (
                <ConnectionForm connector={active} />
              ) : (
                <p className="text-muted-foreground">Select a platform to configure.</p>
              )}
            </Card>
          </div>
        )}

        <p className="mt-4 max-w-2xl text-caption text-muted-foreground">
          Credentials are sent to the Nexus API to test the connection and are not
          stored. Persisting them requires an encrypted store and a key management
          decision that has not been made yet.
        </p>
      </div>
    </>
  )
}

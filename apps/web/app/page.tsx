import Link from "next/link"
import { ArrowRight, CheckCircle2, Clock, GitBranch } from "lucide-react"

import { Topbar } from "@/components/layout/topbar"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { SeverityBadge } from "@/components/common/severity-badge"
import { RunStateBadge } from "@/components/common/run-state-badge"
import { incidents, pipelines, NOW } from "@/lib/demo-data"
import { formatRelative } from "@/lib/utils"

function Stat({
  label,
  value,
  hint,
  icon: Icon,
}: {
  label: string
  value: string
  hint: string
  icon: React.ComponentType<{ className?: string }>
}) {
  return (
    <Card>
      <CardContent className="p-4 pt-4">
        <div className="flex items-center gap-2 text-muted-foreground">
          <Icon className="size-3.5" />
          <span className="text-caption">{label}</span>
        </div>
        <div className="mt-2 text-display tabular-nums">{value}</div>
        <div className="mt-0.5 text-caption text-muted-foreground">{hint}</div>
      </CardContent>
    </Card>
  )
}

export default function OverviewPage() {
  const open = incidents.filter((i) => i.status !== "resolved")

  return (
    <>
      <Topbar
        title="Overview"
        description="Acme Corp · Production"
        actions={
          <Button variant="primary" size="sm" asChild>
            <Link href="/pipelines/new">New pipeline</Link>
          </Button>
        }
      />

      <div className="flex-1 overflow-y-auto p-4">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Stat label="Pipelines" value="4" hint="3 created, 1 adopted" icon={GitBranch} />
          <Stat label="Open incidents" value={String(open.length)} hint="1 awaiting approval" icon={Clock} />
          <Stat label="Autonomous resolutions" value="63%" hint="Last 30 days" icon={CheckCircle2} />
          <Stat label="Median time to diagnose" value="4m 12s" hint="Down from 47m baseline" icon={Clock} />
        </div>

        <section className="mt-6">
          <div className="mb-2 flex items-center justify-between">
            <h2 className="text-h2">Open incidents</h2>
            <Button variant="ghost" size="sm" asChild>
              <Link href="/incidents" className="gap-1 text-muted-foreground">
                View all <ArrowRight className="size-3.5" />
              </Link>
            </Button>
          </div>

          <Card className="divide-y divide-border">
            {open.map((incident) => (
              <Link
                key={incident.id}
                href={`/incidents/${incident.id}`}
                className="flex items-center gap-3 p-3 transition-colors hover:bg-accent/50"
              >
                <SeverityBadge severity={incident.severity} />
                <div className="min-w-0 flex-1">
                  <div className="truncate font-medium">{incident.title}</div>
                  <div className="truncate text-caption text-muted-foreground">
                    {incident.pipelineName} · detected {formatRelative(incident.detectedAt, NOW)}
                  </div>
                </div>
                <span className="hidden shrink-0 font-mono text-caption text-muted-foreground sm:inline">
                  #{incident.number}
                </span>
              </Link>
            ))}
          </Card>
        </section>

        <section className="mt-6">
          <h2 className="mb-2 text-h2">Pipelines</h2>
          <Card className="divide-y divide-border">
            {pipelines.map((p) => (
              <Link
                key={p.id}
                href={`/pipelines/${p.id}`}
                className="flex items-center gap-3 p-3 transition-colors hover:bg-accent/50"
              >
                <div className="min-w-0 flex-1">
                  <div className="truncate font-medium">{p.name}</div>
                  <div className="truncate text-caption text-muted-foreground">
                    {p.schedule.humanized} · {p.target.warehouse} · {p.modelCount} models
                  </div>
                </div>
                <RunStateBadge state={p.lastRun.state} />
              </Link>
            ))}
          </Card>
        </section>
      </div>
    </>
  )
}

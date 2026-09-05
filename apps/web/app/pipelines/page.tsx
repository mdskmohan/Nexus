import Link from "next/link"

import { Topbar } from "@/components/layout/topbar"
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { RunStateBadge } from "@/components/common/run-state-badge"
import { pipelines, NOW } from "@/lib/demo-data"
import { formatDuration, formatRelative } from "@/lib/utils"

export default function PipelinesPage() {
  return (
    <>
      <Topbar
        title="Pipelines"
        description={`${pipelines.length} pipelines across 2 warehouses`}
        actions={
          <Button variant="primary" size="sm" asChild>
            <Link href="/pipelines/new">New pipeline</Link>
          </Button>
        }
      />
      <div className="flex-1 overflow-y-auto p-4">
        <Card className="divide-y divide-border">
          {pipelines.map((p) => (
            <Link
              key={p.id}
              href={`/pipelines/${p.id}`}
              className="flex items-center gap-3 p-3 transition-colors hover:bg-accent/50"
            >
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <span className="truncate font-medium">{p.name}</span>
                  {/* Adopted pipelines carry a partial spec — worth flagging in the list. */}
                  {p.origin === "adopted" ? <Badge tone="info">Adopted</Badge> : null}
                </div>
                <div className="truncate text-caption text-muted-foreground">
                  {p.description}
                </div>
              </div>

              <div className="hidden shrink-0 text-right sm:block">
                <div className="text-caption text-muted-foreground">{p.schedule.humanized}</div>
                <div className="text-caption text-muted-foreground">
                  {p.target.warehouse} · {p.modelCount} models
                </div>
              </div>

              <div className="hidden shrink-0 text-right md:block">
                <div className="text-caption text-muted-foreground">
                  {formatRelative(p.lastRun.startedAt, NOW)}
                </div>
                <div className="text-caption tabular-nums text-muted-foreground">
                  {formatDuration(p.lastRun.durationSeconds)}
                </div>
              </div>

              <RunStateBadge state={p.lastRun.state} />
            </Link>
          ))}
        </Card>
      </div>
    </>
  )
}

import Link from "next/link"

import { Topbar } from "@/components/layout/topbar"
import { Card } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { SeverityBadge } from "@/components/common/severity-badge"
import { incidents, NOW } from "@/lib/demo-data"
import { formatRelative } from "@/lib/utils"

export default function IncidentsPage() {
  return (
    <>
      <Topbar title="Incidents" description="Open and recently resolved" />
      <div className="flex-1 overflow-y-auto p-4">
        <Card className="divide-y divide-border">
          {incidents.map((incident) => (
            <Link
              key={incident.id}
              href={`/incidents/${incident.id}`}
              className="flex items-center gap-3 p-3 transition-colors hover:bg-accent/50"
            >
              <SeverityBadge severity={incident.severity} />
              <div className="min-w-0 flex-1">
                <div className="truncate font-medium">{incident.title}</div>
                <div className="truncate text-caption text-muted-foreground">
                  {incident.pipelineName} · failed at{" "}
                  <span className="font-mono">{incident.failedNode}</span> ·{" "}
                  {formatRelative(incident.detectedAt, NOW)}
                </div>
              </div>
              <Badge tone={incident.status === "awaiting_approval" ? "warning" : "neutral"} className="hidden capitalize sm:inline-flex">
                {incident.status.replace(/_/g, " ")}
              </Badge>
              <span className="shrink-0 font-mono text-caption text-muted-foreground">
                #{incident.number}
              </span>
            </Link>
          ))}
        </Card>
      </div>
    </>
  )
}

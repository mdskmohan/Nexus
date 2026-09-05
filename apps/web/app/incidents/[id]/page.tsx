import Link from "next/link"
import { notFound } from "next/navigation"
import {
  BarChart3,
  Check,
  ChevronLeft,
  Database,
  FileCode2,
  GitPullRequest,
  LayoutDashboard,
  Send,
  ShieldAlert,
  X,
} from "lucide-react"

import { Topbar } from "@/components/layout/topbar"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { SeverityBadge } from "@/components/common/severity-badge"
import { getIncident, incidents, NOW } from "@/lib/demo-data"
import { formatRelative } from "@/lib/utils"
import type { Evidence, Hypothesis, ImpactedEntity } from "@/lib/types"

export function generateStaticParams() {
  return incidents.map((i) => ({ id: i.id }))
}

const IMPACT_ICON: Record<ImpactedEntity["kind"], React.ComponentType<{ className?: string }>> = {
  model: Database,
  dashboard: LayoutDashboard,
  export: Send,
  ml_feature: BarChart3,
}

function EvidenceRow({ evidence }: { evidence: Evidence }) {
  return (
    <li className="flex gap-3 py-3 first:pt-0 last:pb-0">
      <span
        className={
          "mt-0.5 grid size-4 shrink-0 place-items-center rounded-full " +
          (evidence.supports
            ? "bg-success-soft text-success-soft-foreground"
            : "bg-muted text-muted-foreground")
        }
        aria-hidden
      >
        {evidence.supports ? <Check className="size-3" /> : <X className="size-3" />}
      </span>
      <div className="min-w-0">
        <div className="font-medium">{evidence.summary}</div>
        <p className="mt-0.5 text-muted-foreground">{evidence.detail}</p>
        {/* Provenance is shown so an engineer can independently verify the claim. */}
        <div className="mt-1.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-caption text-muted-foreground">
          <span className="font-mono">{evidence.source}</span>
          <span aria-hidden>·</span>
          <span>{formatRelative(evidence.observedAt, NOW)}</span>
        </div>
      </div>
    </li>
  )
}

function HypothesisCard({ hypothesis, rank }: { hypothesis: Hypothesis; rank: number }) {
  const leading = rank === 0
  const pct = Math.round(hypothesis.confidence * 100)

  return (
    <Card className={leading ? "border-border-strong" : undefined}>
      <CardHeader className="gap-2">
        <div className="flex items-start gap-3">
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <CardTitle className="truncate">{hypothesis.title}</CardTitle>
              {leading ? <Badge tone="primary">Leading</Badge> : null}
            </div>
            <div className="mt-1 flex items-center gap-2">
              <div
                className="h-1 w-24 overflow-hidden rounded-full bg-muted"
                role="img"
                aria-label={`Confidence ${pct} percent`}
              >
                <div
                  className={leading ? "h-full bg-primary" : "h-full bg-border-strong"}
                  style={{ width: `${pct}%` }}
                />
              </div>
              <span className="text-caption tabular-nums text-muted-foreground">
                {pct}% confidence
              </span>
            </div>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <ul className="divide-y divide-border">
          {hypothesis.evidence.map((e) => (
            <EvidenceRow key={e.id} evidence={e} />
          ))}
        </ul>
      </CardContent>
    </Card>
  )
}

export default function IncidentPage({ params }: { params: { id: string } }) {
  const incident = getIncident(params.id)
  if (!incident) notFound()

  const ranked = [...incident.hypotheses].sort((a, b) => b.confidence - a.confidence)
  const remediation = incident.remediation

  return (
    <>
      <Topbar
        title={`Incident #${incident.number}`}
        description={`${incident.pipelineName} · detected ${formatRelative(incident.detectedAt, NOW)}`}
        actions={
          <Button variant="ghost" size="sm" asChild>
            <Link href="/incidents" className="gap-1 text-muted-foreground">
              <ChevronLeft className="size-3.5" /> Incidents
            </Link>
          </Button>
        }
      />

      <div className="flex-1 overflow-y-auto">
        <div className="border-b border-border p-4">
          <div className="flex flex-wrap items-center gap-2">
            <SeverityBadge severity={incident.severity} />
            <Badge tone="warning" className="capitalize">
              {incident.status.replace(/_/g, " ")}
            </Badge>
            <span className="text-caption text-muted-foreground">
              failed at <span className="font-mono">{incident.failedNode}</span>
            </span>
          </div>
          <h2 className="mt-2 text-h1">{incident.title}</h2>
        </div>

        <div className="grid gap-4 p-4 lg:grid-cols-[minmax(0,1fr)_320px]">
          {/* ── Investigation ── */}
          <section className="min-w-0">
            <h3 className="mb-2 text-h2">Investigation</h3>
            <p className="mb-3 text-caption text-muted-foreground">
              Hypotheses are ranked by the weight of collected evidence. Every claim below
              names the system it was read from.
            </p>
            <div className="flex flex-col gap-3">
              {ranked.map((h, i) => (
                <HypothesisCard key={h.id} hypothesis={h} rank={i} />
              ))}
            </div>

            {remediation ? (
              <>
                <h3 className="mb-2 mt-6 text-h2">Proposed remediation</h3>
                <Card>
                  <CardHeader>
                    <CardTitle>{remediation.summary}</CardTitle>
                    <p className="mt-1 text-body text-muted-foreground">
                      {remediation.rationale}
                    </p>
                  </CardHeader>
                  <CardContent className="flex flex-col gap-3">
                    <div className="overflow-x-auto rounded-md border border-border bg-muted/40">
                      <pre className="p-3 font-mono text-caption leading-relaxed">
                        {remediation.diff.split("\n").map((line, i) => (
                          <div
                            key={i}
                            className={
                              line.startsWith("+") && !line.startsWith("+++")
                                ? "bg-success-soft text-success-soft-foreground"
                                : line.startsWith("-") && !line.startsWith("---")
                                  ? "bg-danger-soft text-danger-soft-foreground"
                                  : "text-muted-foreground"
                            }
                          >
                            {line || " "}
                          </div>
                        ))}
                      </pre>
                    </div>

                    <div className="flex items-center gap-2 rounded-md border border-border bg-success-soft/40 p-2.5">
                      <Check className="size-4 shrink-0 text-success" />
                      <div className="min-w-0 text-caption">
                        <span className="font-medium text-foreground">
                          {remediation.validation.testsPassed}/{remediation.validation.testsTotal} tests
                          passed
                        </span>
                        <span className="text-muted-foreground">
                          {" "}
                          in sandbox{" "}
                          <span className="font-mono">{remediation.validation.sandbox}</span>
                        </span>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              </>
            ) : null}
          </section>

          {/* ── Impact and action ── */}
          <aside className="flex min-w-0 flex-col gap-4">
            <Card>
              <CardHeader>
                <CardTitle>Impact</CardTitle>
              </CardHeader>
              <CardContent>
                <ul className="flex flex-col gap-2.5">
                  {incident.impact.map((entity) => {
                    const Icon = IMPACT_ICON[entity.kind]
                    return (
                      <li key={entity.id} className="flex items-center gap-2.5">
                        <Icon className="size-4 shrink-0 text-muted-foreground" />
                        <div className="min-w-0 flex-1">
                          <div className="truncate">{entity.name}</div>
                          <div className="truncate text-caption capitalize text-muted-foreground">
                            {entity.kind.replace(/_/g, " ")}
                          </div>
                        </div>
                        <SeverityBadge severity={entity.criticality} />
                      </li>
                    )
                  })}
                </ul>
              </CardContent>
            </Card>

            {remediation ? (
              <Card>
                <CardHeader>
                  <CardTitle>Action</CardTitle>
                </CardHeader>
                <CardContent className="flex flex-col gap-3">
                  {/* The gate from ADR-003 is surfaced, not hidden — it is the product. */}
                  <div className="flex items-start gap-2 rounded-md border border-border bg-muted/50 p-2.5">
                    <ShieldAlert className="mt-0.5 size-4 shrink-0 text-muted-foreground" />
                    <p className="text-caption text-muted-foreground">
                      This action modifies a transformation and requires{" "}
                      <span className="font-medium text-foreground">
                        autonomy level {remediation.requiredLevel}
                      </span>
                      . Your environment is at level 2, so it needs approval.
                    </p>
                  </div>

                  <Button variant="primary" className="w-full justify-center">
                    <GitPullRequest className="size-4" />
                    Open pull request
                  </Button>
                  <Button variant="outline" className="w-full justify-center">
                    <FileCode2 className="size-4" />
                    View compiled SQL
                  </Button>
                </CardContent>
              </Card>
            ) : null}
          </aside>
        </div>
      </div>
    </>
  )
}

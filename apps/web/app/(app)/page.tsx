"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  ArrowRight, Bot, Cable, CheckCircle2, Circle, GitBranch, Inbox, Network, Table2, Users, Workflow,
} from "lucide-react";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { PageHeader } from "@/components/ui/page-header";
import { StatCard } from "@/components/ui/stat-card";
import { StatusPill } from "@/components/ui/status-pill";
import { api, can, type Connection, type GraphSummary, type HumanRequest } from "@/lib/api";
import { useMe } from "@/lib/me";
import { cn } from "@/lib/utils";

function Step({ done, title, body, href, cta }: { done: boolean; title: string; body: string; href?: string; cta?: string }) {
  return (
    <div className="flex items-start gap-3 px-5 py-4">
      {done ? <CheckCircle2 className="mt-0.5 size-5 shrink-0 text-success" /> : <Circle className="mt-0.5 size-5 shrink-0 text-border-strong" />}
      <div className="min-w-0 flex-1">
        <p className={cn("font-medium", done ? "text-muted-foreground line-through decoration-muted-foreground/40" : "text-foreground")}>{title}</p>
        <p className="text-caption text-muted-foreground">{body}</p>
      </div>
      {href && !done && (
        <Link href={href} className="inline-flex items-center gap-1 text-caption font-medium text-primary hover:underline">
          {cta}<ArrowRight className="size-3.5" />
        </Link>
      )}
    </div>
  );
}

export default function Home() {
  const me = useMe();
  const seesGraph = can(me, "approve_graph") || can(me, "build_agents") || can(me, "manage_connections");
  const [summary, setSummary] = useState<GraphSummary | null>(null);
  const [conns, setConns] = useState<Connection[]>([]);
  const [requests, setRequests] = useState<HumanRequest[]>([]);
  const [team, setTeam] = useState(0);

  useEffect(() => {
    api.get<HumanRequest[]>("/requests").then(setRequests).catch(() => {});
    api.get<unknown[]>("/team").then((t) => setTeam(t.length)).catch(() => {});
    if (seesGraph) {
      api.get<GraphSummary>("/graph/summary").then(setSummary).catch(() => {});
      api.get<Connection[]>("/connections").then(setConns).catch(() => {});
    }
  }, [seesGraph]);

  const approvedTables = summary?.counts.table?.approved ?? 0;
  const approvedJoins = summary?.counts.join?.approved ?? 0;
  const proposed = Object.entries(summary?.counts ?? {})
    .filter(([kind]) => kind !== "column").reduce((n, [, s]) => n + (s?.proposed ?? 0), 0);
  const firstName = me.user.name.split(" ")[0];

  return (
    <>
      <PageHeader title={`Welcome back, ${firstName}`} description="Your workspace at a glance." />

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Waiting for you" value={requests.length} icon={Inbox} tone={requests.length ? "warning" : "neutral"}
          sub={requests.length ? "Approvals and questions from runs" : "Nothing needs a decision"} />
        <StatCard label="Graph version" value={summary?.version ?? 0} icon={GitBranch} tone="primary"
          sub={`${approvedTables} tables, ${approvedJoins} joins approved`} />
        <StatCard label="Waiting for review" value={proposed} icon={Network} tone={proposed ? "info" : "neutral"}
          sub="Proposals in the knowledge graph" />
        <StatCard label="Connections" value={conns.length} icon={Cable} tone="success"
          sub={`${conns.filter((c) => c.collect_status === "done").length} read successfully`} />
      </div>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1.5fr)_minmax(0,1fr)]">
        <Card>
          <CardHeader title="Getting started" description="Five steps from an empty workspace to your first agent." />
          <div className="divide-y divide-border">
            <Step done={me.model_configured} title="Connect an AI model" body="Claude, GPT, Gemini or a model on your own server." href={can(me, "manage_ai") ? "/settings?tab=ai" : undefined} cta="Settings" />
            <Step done={team > 1} title="Invite your team" body="Give each person a role: steward, developer, analyst or viewer." href={can(me, "manage_people") ? "/settings?tab=team" : undefined} cta="Invite" />
            <Step done={conns.some((c) => c.collect_status === "done")} title="Connect your warehouses" body="Nexus reads tables and columns with read-only queries." href={can(me, "manage_connections") ? "/connections" : undefined} cta="Connect" />
            <Step done={approvedTables > 0} title="Approve the knowledge graph" body="A steward approves tables, joins and metrics before agents use them." href={seesGraph ? "/knowledge" : undefined} cta="Review" />
            <Step done={false} title="Build your first agent" body="Agent Studio arrives in the next milestone." />
          </div>
        </Card>

        <div className="space-y-6">
          <Card>
            <CardHeader title="Waiting for you" actions={<Link href="/approvals" className="text-caption font-medium text-primary hover:underline">Open inbox</Link>} />
            <CardBody className="space-y-2">
              {requests.length === 0 ? <p className="text-body text-muted-foreground">Nothing is waiting for you.</p>
                : requests.slice(0, 4).map((q) => (
                  <Link key={q.id} href="/approvals" className="flex items-center justify-between gap-3 rounded-md border border-border px-3 py-2 hover:bg-muted/40">
                    <span className="truncate text-body text-foreground">{q.title}</span>
                    <StatusPill tone={q.kind === "approval" ? "warning" : "info"} dot>{q.kind === "approval" ? "Approve" : "Answer"}</StatusPill>
                  </Link>
                ))}
            </CardBody>
          </Card>
          <Card className="overflow-hidden">
            <div className="relative px-5 py-5">
              <div aria-hidden className="pointer-events-none absolute inset-0 opacity-70 [background:radial-gradient(ellipse_at_top_right,hsl(var(--primary-soft))_0%,transparent_65%)]" />
              <div className="relative space-y-2">
                <div className="flex items-center gap-2 text-primary"><Workflow className="size-4" /><span className="text-caption font-semibold uppercase tracking-wider">Coming next</span></div>
                <p className="text-h2 text-foreground">Agent Studio</p>
                <p className="text-body text-muted-foreground">Build agents on a visual canvas over your approved graph, test them step by step, and publish them to your team.</p>
                <div className="flex flex-wrap gap-2 pt-1">
                  <StatusPill tone="neutral" icon={<Table2 />}>SQL across warehouses</StatusPill>
                  <StatusPill tone="neutral" icon={<Users />}>People in the loop</StatusPill>
                  <StatusPill tone="neutral" icon={<Bot />}>Any AI model</StatusPill>
                </div>
              </div>
            </div>
          </Card>
        </div>
      </div>
    </>
  );
}

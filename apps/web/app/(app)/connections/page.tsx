"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useState } from "react";
import { ArrowRight, Cable, CheckCircle2, Database, History, Loader2, Play, Plus, XCircle, Zap } from "lucide-react";
import { ConnectionSheet } from "@/components/connections/connection-sheet";
import { KindMark, VerifiedBadge } from "@/components/connections/kinds";
import { announceRunStarted, RUN_FINISHED } from "@/components/connections/run-watcher";
import {
  assets, FAILURE_TITLE, isActive, PHASE_LABEL, RunProgress, RunStatusPill,
} from "@/components/connections/run-ui";
import { RunsTable, type RunFilter } from "@/components/connections/runs-table";
import { Button } from "@/components/ui/button";
import { Callout } from "@/components/ui/callout";
import { Card } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { PageHeader } from "@/components/ui/page-header";
import { StatCard } from "@/components/ui/stat-card";
import { Tabs } from "@/components/ui/tabs";
import { useToast } from "@/components/ui/toast";
import { api, can, type Connection, type ConnectorSpec, type RunsSummary } from "@/lib/api";
import { when } from "@/lib/format";
import { useMe } from "@/lib/me";

type Tab = "sources" | "runs";
const FILTERS: RunFilter[] = ["all", "active", "succeeded", "failed", "cancelled"];

export default function ConnectionsPage() {
  return <Suspense><Connections /></Suspense>;
}

function Connections() {
  const me = useMe();
  const manage = can(me, "manage_connections");
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const tab: Tab = params.get("tab") === "runs" ? "runs" : "sources";
  const filter = (FILTERS.includes(params.get("status") as RunFilter) ? params.get("status") : "all") as RunFilter;
  const [specs, setSpecs] = useState<ConnectorSpec[]>([]);
  const [conns, setConns] = useState<Connection[] | null>(null);
  const [summary, setSummary] = useState<RunsSummary | null>(null);
  const [adding, setAdding] = useState(false);

  const go = useCallback((next: Record<string, string | null>) => {
    const q = new URLSearchParams(params.toString());
    for (const [k, v] of Object.entries(next)) if (v === null) q.delete(k); else q.set(k, v);
    router.replace(`${pathname}${q.size ? `?${q}` : ""}`, { scroll: false });
  }, [params, pathname, router]);

  const load = useCallback(() => Promise.all([
    api.get<Connection[]>("/connections").then(setConns),
    api.get<RunsSummary>("/connections/runs/summary").then(setSummary),
  ]).catch(() => {}), []);

  useEffect(() => { api.get<ConnectorSpec[]>("/connections/kinds").then(setSpecs); load(); }, [load]);
  const running = conns?.some((c) => isActive(c.last_run));
  useEffect(() => {
    const t = setInterval(load, running ? 2000 : 15000);
    return () => clearInterval(t);
  }, [load, running]);
  useEffect(() => {
    const refresh = () => load();
    window.addEventListener(RUN_FINISHED, refresh);
    return () => window.removeEventListener(RUN_FINISHED, refresh);
  }, [load]);

  const showRuns = (status: RunFilter) => go({ tab: "runs", status: status === "all" ? null : status });

  return (
    <>
      <PageHeader title="Connections" description="The warehouses Nexus reads, and every run that reads them. Nexus only ever sends read-only queries."
        actions={manage && <Button onClick={() => setAdding(true)}><Plus />Add a connection</Button>} />

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <button className="rounded-lg text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" onClick={() => go({ tab: null, status: null })}>
          <StatCard label="Sources" value={conns?.length ?? "–"} icon={Database} tone="primary"
            sub={conns ? `${conns.filter((c) => c.last_success).length} read successfully` : " "} />
        </button>
        <button className="rounded-lg text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" onClick={() => showRuns("active")}>
          <StatCard label="Running now" value={summary?.active ?? "–"} icon={Loader2} tone="info"
            sub={summary?.active ? "Updating live" : "Nothing running"} />
        </button>
        <button className="rounded-lg text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" onClick={() => showRuns("succeeded")}>
          <StatCard label="Succeeded" value={summary?.succeeded_24h ?? "–"} icon={CheckCircle2} tone="success" sub="In the last 24 hours" />
        </button>
        <button className="rounded-lg text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" onClick={() => showRuns("failed")}>
          <StatCard label="Failed" value={summary?.failed_24h ?? "–"} icon={XCircle} tone={summary?.failed_24h ? "danger" : "neutral"}
            sub={summary?.failed_24h ? "Open each run to see why" : "In the last 24 hours"} />
        </button>
      </div>

      <Tabs value={tab} onChange={(t) => go({ tab: t === "sources" ? null : t, status: null })}
        tabs={[{ id: "sources", label: "Sources", icon: <Cable />, count: conns?.length },
               { id: "runs", label: "Runs", icon: <History />, count: summary?.active || undefined }]} />

      {tab === "runs" ? (
        <RunsTable filter={filter} onFilter={(f) => go({ status: f === "all" ? null : f })} />
      ) : conns === null ? null : conns.length === 0 ? (
        <Card>
          <EmptyState icon={Cable} title="No connections yet"
            description={<>Connect Snowflake, Databricks, SQL Server, Oracle, BigQuery and more. To try Nexus without a warehouse,
              run <code>uv run nexus-seed-demo --email {me.user.email}</code> in <code>services/api</code>.</>}
            action={manage && <Button onClick={() => setAdding(true)}><Plus />Add a connection</Button>} />
        </Card>
      ) : (
        <div className="grid gap-4 lg:grid-cols-2">
          {conns.map((c) => <SourceCard key={c.id} conn={c} spec={specs.find((s) => s.kind === c.kind)} manage={manage} onChange={load} />)}
        </div>
      )}

      {tab === "sources" && conns?.some((c) => c.last_success) && (
        <Link href="/knowledge" className="group flex items-center justify-between rounded-lg border border-primary/20 bg-primary-soft px-5 py-4 text-primary">
          <span className="text-body font-medium">Everything Nexus reads arrives as a proposal. Review it in the knowledge graph.</span>
          <ArrowRight className="size-4 transition-transform group-hover:translate-x-0.5" />
        </Link>
      )}

      {manage && (
        <ConnectionSheet open={adding} specs={specs} onClose={() => setAdding(false)}
          onSaved={(id) => router.push(`/connections/${id}?new=1`)} />
      )}
    </>
  );
}

function SourceCard({ conn: c, spec, manage, onChange }: {
  conn: Connection; spec?: ConnectorSpec; manage: boolean; onChange: () => void;
}) {
  const router = useRouter();
  const toast = useToast();
  const [testing, setTesting] = useState(false);
  const [starting, setStarting] = useState(false);
  const run = c.last_run;
  const active = isActive(run);
  const href = `/connections/${c.id}`;

  async function test(e: React.MouseEvent) {
    e.stopPropagation();
    setTesting(true);
    try {
      const r = await api.post<{ ok: boolean; message: string }>(`/connections/${c.id}/test`);
      toast({ tone: r.ok ? "success" : "danger", title: r.ok ? `${c.label}: connection works` : `${c.label}: test failed`, description: r.message });
      onChange();
    } catch (err) { toast({ tone: "danger", title: "Could not test", description: (err as Error).message }); }
    finally { setTesting(false); }
  }

  async function start(e: React.MouseEvent) {
    e.stopPropagation();
    setStarting(true);
    try {
      const { run_id } = await api.post<{ run_id: string }>(`/connections/${c.id}/collect`);
      announceRunStarted(run_id);
      router.push(`/connections/runs/${run_id}`);
    } catch (err) {
      toast({ tone: "danger", title: "Could not start a run", description: (err as Error).message });
      setStarting(false);
    }
  }

  return (
    <Card role="link" tabIndex={0} onClick={() => router.push(href)} onKeyDown={(e) => { if (e.key === "Enter") router.push(href); }}
      className="group flex cursor-pointer flex-col transition-shadow hover:shadow-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
      <div className="flex items-start justify-between gap-3 px-5 pt-5">
        <div className="flex min-w-0 items-start gap-3">
          <KindMark kind={c.kind} size="lg" />
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <p className="truncate text-h2 text-foreground group-hover:text-primary">{c.label}</p>
              <VerifiedBadge verified={c.verified} />
            </div>
            <p className="truncate text-caption text-muted-foreground">
              {spec?.name ?? c.kind}{c.config.database ? ` · ${c.config.database}` : ""}{c.config.host ? ` · ${c.config.host}` : ""}
            </p>
          </div>
        </div>
        {run ? <RunStatusPill run={run} /> : <span className="whitespace-nowrap text-caption text-muted-foreground">{c.collected_at ? "No runs yet" : "Never run"}</span>}
      </div>

      <div className="flex-1 space-y-3 px-5 py-4">
        {run && active ? (
          <div className="space-y-1.5">
            <div className="flex items-center justify-between text-caption">
              <span className="text-muted-foreground">{run.cancel_requested ? "Stopping…" : PHASE_LABEL[run.phase]}</span>
              <span className="num font-medium text-foreground">{Math.round(run.progress)}%</span>
            </div>
            <RunProgress run={run} />
          </div>
        ) : run?.status === "failed" ? (
          <Callout tone="danger" title={FAILURE_TITLE[run.error_kind ?? "warehouse"]}>
            <span className="line-clamp-2">{run.hint}</span>
          </Callout>
        ) : null}
        {c.last_success ? (
          <p className="text-body text-muted-foreground">
            <span className="text-foreground">{assets(c.last_success.stats)}</span>
            <span className="text-caption"> · read {when(c.last_success.finished_at)}</span>
          </p>
        ) : c.collected_at && c.collect_msg ? (
          // Read before run history was kept.
          <p className="text-body text-muted-foreground">{c.collect_msg}<span className="text-caption"> · {when(c.collected_at)}</span></p>
        ) : !run && (
          <p className="text-body text-muted-foreground">Test the connection, then run it to read its tables.</p>
        )}
        {c.last_test_ok === false && !active && run?.status !== "failed" && (
          <p className="text-caption text-danger">The last connection test failed. Open the connection for details.</p>
        )}
      </div>

      {manage && (
        <div className="flex items-center justify-end gap-2 border-t border-border bg-muted/30 px-5 py-3">
          <span className="mr-auto text-caption text-muted-foreground">{run ? `Last run ${when(run.created_at)}` : "Not run yet"}</span>
          <Button variant="outline" size="sm" disabled={testing} onClick={test}>
            {testing ? <Loader2 className="animate-spin" /> : <Zap />}Test
          </Button>
          <Button size="sm" disabled={active || starting} onClick={start}>
            {starting || active ? <Loader2 className="animate-spin" /> : <Play />}{active ? "Running" : "Run now"}
          </Button>
        </div>
      )}
    </Card>
  );
}

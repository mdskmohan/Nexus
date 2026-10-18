"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import {
  ArrowLeft, Ban, CheckCircle2, Columns3, Eye, GitMerge, KeyRound, Layers, Loader2, Network, PlusCircle,
  RotateCcw, Table2, Timer, Trash, XCircle,
} from "lucide-react";
import { KindMark } from "@/components/connections/kinds";
import { LogConsole } from "@/components/connections/log-console";
import { announceRunStarted } from "@/components/connections/run-watcher";
import {
  elapsed, FAILURE_TITLE, isActive, PHASE_LABEL, PHASES, RunProgress, RunStatusPill, seconds, TRIGGER_LABEL,
} from "@/components/connections/run-ui";
import { useRunStream } from "@/components/connections/use-run-stream";
import { Button } from "@/components/ui/button";
import { Callout } from "@/components/ui/callout";
import { Card, CardBody } from "@/components/ui/card";
import { useToast } from "@/components/ui/toast";
import { api, can, type CollectRun } from "@/lib/api";
import { useCrumb } from "@/lib/crumbs";
import { useMe } from "@/lib/me";
import { cn } from "@/lib/utils";

export default function RunPage() {
  const { runId } = useParams<{ runId: string }>();
  const me = useMe();
  const manage = can(me, "manage_connections");
  const router = useRouter();
  const toast = useToast();
  const { run, logs, state } = useRunStream(runId);
  const [busy, setBusy] = useState<"cancel" | "retry" | null>(null);
  const [now, setNow] = useState(() => Date.now());
  useCrumb(`/connections/runs/${runId}`, run ? `Run ${new Date(run.created_at).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" })}` : null);

  const active = isActive(run);
  useEffect(() => {
    if (!active) return;
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, [active]);

  async function cancel() {
    setBusy("cancel");
    try { await api.post(`/connections/runs/${runId}/cancel`); }
    catch (err) { toast({ tone: "danger", title: "Could not cancel", description: (err as Error).message }); }
    finally { setBusy(null); }
  }

  async function retry() {
    setBusy("retry");
    try {
      const { run_id } = await api.post<{ run_id: string }>(`/connections/runs/${runId}/retry`);
      announceRunStarted(run_id);
      router.push(`/connections/runs/${run_id}`);
    } catch (err) {
      toast({ tone: "danger", title: "Could not start the run again", description: (err as Error).message });
      setBusy(null);
    }
  }

  if (state === "missing") {
    return (
      <Card><CardBody className="space-y-3 py-10 text-center">
        <p className="text-h2 text-foreground">This run no longer exists.</p>
        <p className="text-body text-muted-foreground">Runs are removed with their connection.</p>
        <Link href="/connections?tab=runs" className="text-body font-medium text-primary hover:underline">All runs</Link>
      </CardBody></Card>
    );
  }
  if (!run) return <div className="flex items-center gap-2 py-10 text-body text-muted-foreground"><Loader2 className="size-4 animate-spin" />Loading the run…</div>;

  const st = run.stats;
  const took = seconds(run, now);
  const conn = `/connections/${run.connection_id}`;

  return (
    <>
      <Link href={conn} className="inline-flex items-center gap-1.5 text-caption text-muted-foreground hover:text-foreground">
        <ArrowLeft className="size-3.5" />{run.connection_label}
      </Link>

      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="flex min-w-0 items-start gap-4">
          <KindMark kind={run.connection_kind ?? ""} size="lg" />
          <div className="min-w-0 space-y-1.5">
            <div className="flex flex-wrap items-center gap-2.5">
              <h1 className="text-h1 tracking-tight text-foreground">Reading {run.connection_label}</h1>
              <RunStatusPill run={run} />
            </div>
            <p className="flex flex-wrap items-center gap-x-3 gap-y-1 text-caption text-muted-foreground">
              <span>{TRIGGER_LABEL[run.trigger]}{run.requested_by_name ? ` by ${run.requested_by_name}` : ""}</span>
              <span title="Queued at">{new Date(run.created_at).toLocaleString()}</span>
              <span className="inline-flex items-center gap-1"><Timer className="size-3.5" /><span className="num">{elapsed(took)}</span></span>
              <span className="font-mono">#{run.id.slice(0, 8)}</span>
            </p>
          </div>
        </div>
        {manage && (
          <div className="flex shrink-0 items-center gap-2">
            {active ? (
              <Button variant="outline" size="sm" disabled={busy !== null || run.cancel_requested} onClick={cancel}>
                {busy === "cancel" || run.cancel_requested ? <Loader2 className="animate-spin" /> : <Ban />}
                {run.cancel_requested ? "Stopping…" : "Cancel run"}
              </Button>
            ) : (
              <Button size="sm" disabled={busy !== null} onClick={retry}>
                {busy === "retry" ? <Loader2 className="animate-spin" /> : <RotateCcw />}{run.status === "failed" ? "Retry" : "Run again"}
              </Button>
            )}
          </div>
        )}
      </div>

      {run.status === "failed" && (
        <Callout tone="danger" title={FAILURE_TITLE[run.error_kind ?? "warehouse"] ?? "The run failed"}
          action={manage && <Link href={conn} className="shrink-0 self-center text-caption font-medium underline underline-offset-2">Check the settings</Link>}>
          <p>{run.hint}</p>
          {run.error && <pre className="mt-2 max-h-40 overflow-auto whitespace-pre-wrap break-words rounded-md bg-background/60 px-3 py-2 font-mono text-caption text-foreground">{run.error}</pre>}
        </Callout>
      )}
      {run.status === "cancelled" && (
        <Callout tone="warning" title="This run was cancelled">
          {st.new_tables !== undefined ? "Tables it had saved stay in the knowledge graph for review." : "It stopped before saving anything; the knowledge graph is unchanged."}
        </Callout>
      )}
      {run.status === "succeeded" && (
        <Callout tone="success" title={`Read in ${elapsed(took)}`}
          action={<Link href="/knowledge" className="shrink-0 self-center text-caption font-medium underline underline-offset-2">Review in the knowledge graph</Link>}>
          {st.new_tables ? `${st.new_tables} new tables are waiting for review.` : "Nothing new: everything it found was already known."}
          {st.removed_tables ? ` ${st.removed_tables} tables are no longer in the warehouse.` : ""}
        </Callout>
      )}

      <Card>
        <CardBody className="space-y-5">
          <div className="space-y-2">
            <div className="flex items-baseline justify-between gap-3">
              <p className="text-body font-medium text-foreground">
                {run.status === "running" && run.cancel_requested ? "Stopping at the next safe point…" : active ? PHASE_LABEL[run.phase]
                  : run.status === "succeeded" ? "Complete" : run.status === "failed" ? `Stopped while ${PHASE_LABEL[run.phase].toLowerCase()}`
                  : "Cancelled"}
                {run.phase === "discover" && st.schemas_total ? <span className="num ml-2 text-caption font-normal text-muted-foreground">schema {st.schemas_read ?? 0} of {st.schemas_total}</span> : null}
                {run.phase === "graph" && st.tables_saved !== undefined && st.tables !== undefined ? <span className="num ml-2 text-caption font-normal text-muted-foreground">{st.tables_saved} of {(st.tables ?? 0) + (st.views ?? 0)} saved</span> : null}
              </p>
              <span className="num text-h2 text-foreground">{run.status === "succeeded" ? 100 : Math.round(run.progress)}%</span>
            </div>
            <RunProgress run={run} className="h-2" />
          </div>
          <Stepper run={run} />
        </CardBody>
      </Card>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Metric label="Schemas" value={st.schemas} icon={Layers} />
        <Metric label="Tables" value={st.tables} icon={Table2} strong />
        <Metric label="Views" value={st.views} icon={Eye} />
        <Metric label="Columns" value={st.columns} icon={Columns3} />
        <Metric label="Foreign keys" value={st.foreign_keys} icon={KeyRound} />
        <Metric label="New" value={st.new_tables} icon={PlusCircle} tone="text-success" />
        <Metric label="No longer found" value={st.removed_tables} icon={Trash} tone={st.removed_tables ? "text-warning" : undefined} />
        <Metric label="Joins suggested" value={st.joins_suggested} icon={GitMerge} tone="text-primary" />
      </div>

      <LogConsole logs={logs} state={state} fileName={`nexus-run-${run.id.slice(0, 8)}.log`} />
    </>
  );
}

function Metric({ label, value, icon: Icon, strong, tone }: {
  label: string; value: number | undefined; icon: typeof Layers; strong?: boolean; tone?: string;
}) {
  return (
    <div className="rounded-lg border border-border bg-card px-3.5 py-3">
      <div className="flex items-center gap-1.5 text-caption text-muted-foreground"><Icon className={cn("size-3.5", tone)} />{label}</div>
      <p className={cn("num mt-1 text-h2", value === undefined ? "text-muted-foreground/50" : strong ? "text-foreground" : "text-foreground", tone && value ? tone : "")}>
        {value ?? "–"}
      </p>
    </div>
  );
}

function Stepper({ run }: { run: CollectRun }) {
  const current = run.phase === "done" ? PHASES.length : PHASES.findIndex((p) => p.id === run.phase);
  return (
    <ol className="grid gap-3 sm:grid-cols-5">
      {PHASES.map((p, i) => {
        const done = run.status === "succeeded" || i < current;
        const here = i === current && run.status !== "succeeded";
        const broke = here && (run.status === "failed" || run.status === "cancelled");
        const working = here && run.status === "running";
        const Icon = p.icon;
        return (
          <li key={p.id} className="flex items-start gap-2.5">
            <span className={cn("flex size-8 shrink-0 items-center justify-center rounded-full border transition-colors",
              done ? "border-success/30 bg-success-soft text-success"
                : broke ? (run.status === "failed" ? "border-danger/30 bg-danger-soft text-danger" : "border-warning/30 bg-warning-soft text-warning")
                : working ? "border-primary/40 bg-primary-soft text-primary"
                : "border-border bg-muted/40 text-muted-foreground/60")}>
              {done ? <CheckCircle2 className="size-4" /> : broke ? (run.status === "failed" ? <XCircle className="size-4" /> : <Ban className="size-4" />)
                : working ? <Loader2 className="size-4 animate-spin" /> : <Icon className="size-4" />}
            </span>
            <span className="min-w-0">
              <span className={cn("block text-body font-medium", done || here ? "text-foreground" : "text-muted-foreground")}>{p.label}</span>
              <span className="block text-caption text-muted-foreground">{p.detail}</span>
            </span>
          </li>
        );
      })}
      {run.status === "queued" && (
        <li className="col-span-full flex items-center gap-2 text-caption text-muted-foreground">
          <Network className="size-3.5" />Waiting for a worker to pick this run up.
        </li>
      )}
    </ol>
  );
}

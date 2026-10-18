"use client";

import {
  Ban, CheckCircle2, CircleDashed, Clock, GitMerge, KeyRound, Loader2, Network, Plug, ScanSearch, XCircle,
  type LucideIcon,
} from "lucide-react";
import { StatusPill, type Tone } from "@/components/ui/status-pill";
import type { CollectPhase, CollectRun, CollectRunStatus, CollectStats } from "@/lib/api";
import { plural } from "@/lib/format";
import { cn } from "@/lib/utils";

export const RUN_STATUS: Record<CollectRunStatus, { label: string; tone: Tone; icon: LucideIcon; bar: string }> = {
  queued: { label: "Queued", tone: "neutral", icon: Clock, bar: "bg-muted-foreground/40" },
  running: { label: "Running", tone: "info", icon: Loader2, bar: "bg-primary" },
  succeeded: { label: "Succeeded", tone: "success", icon: CheckCircle2, bar: "bg-success" },
  failed: { label: "Failed", tone: "danger", icon: XCircle, bar: "bg-danger" },
  cancelled: { label: "Cancelled", tone: "warning", icon: Ban, bar: "bg-warning" },
};

export const ACTIVE: CollectRunStatus[] = ["queued", "running"];
export const isActive = (run: Pick<CollectRun, "status"> | null | undefined) => !!run && ACTIVE.includes(run.status);

/** The phases of a run, in order, as the stepper shows them. */
export const PHASES: { id: Exclude<CollectPhase, "queued" | "done">; label: string; detail: string; icon: LucideIcon }[] = [
  { id: "connect", label: "Connect", detail: "Sign in to the warehouse", icon: Plug },
  { id: "discover", label: "Discover", detail: "Read schemas, tables, views and columns", icon: ScanSearch },
  { id: "keys", label: "Keys", detail: "Read declared foreign keys", icon: KeyRound },
  { id: "graph", label: "Save", detail: "Write proposals to the knowledge graph", icon: Network },
  { id: "joins", label: "Joins", detail: "Suggest joins from names and data", icon: GitMerge },
];

export const PHASE_LABEL: Record<CollectPhase, string> = {
  queued: "Waiting for a worker", connect: "Connecting", discover: "Discovering tables", keys: "Reading keys",
  graph: "Saving to the knowledge graph", joins: "Suggesting joins", done: "Done",
};

export const FAILURE_TITLE: Record<string, string> = {
  auth: "Nexus could not sign in",
  network: "Nexus could not reach the server",
  permission: "Not allowed to read the catalogue",
  not_found: "Something named in the settings was not found",
  warehouse: "The warehouse returned an error",
};

export const TRIGGER_LABEL: Record<CollectRun["trigger"], string> = {
  manual: "Started by hand", retry: "Retry", setup: "Initial read", schedule: "Scheduled",
};

export function RunStatusPill({ run, className }: { run: Pick<CollectRun, "status" | "cancel_requested">; className?: string }) {
  const s = RUN_STATUS[run.status];
  const Icon = s.icon;
  const label = run.status === "running" && run.cancel_requested ? "Cancelling" : s.label;
  return (
    <StatusPill tone={s.tone} className={className}
      icon={run.status === "queued" ? <CircleDashed /> : <Icon className={cn(run.status === "running" && "animate-spin")} />}>
      {label}
    </StatusPill>
  );
}

/** A progress bar; a queued run shows a moving stripe since there is nothing to measure yet. */
export function RunProgress({ run, className }: { run: Pick<CollectRun, "status" | "progress">; className?: string }) {
  const value = run.status === "succeeded" ? 100 : Math.round(run.progress);
  return (
    <div role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={value}
      className={cn("relative h-1.5 w-full overflow-hidden rounded-full bg-muted", className)}>
      {run.status === "queued" ? (
        <div className="absolute inset-y-0 w-1/3 animate-progress-slide rounded-full bg-muted-foreground/30" />
      ) : (
        <div className={cn("h-full rounded-full transition-[width] duration-500 ease-out", RUN_STATUS[run.status].bar,
          run.status === "running" && "progress-stripes")} style={{ width: `${Math.max(value, 2)}%` }} />
      )}
    </div>
  );
}

/** "4 tables · 16 columns · 3 joins", the assets a run found. */
export function assets(stats: CollectStats | undefined): string {
  if (!stats || stats.tables === undefined) return "";
  const parts = [plural(stats.tables, "table")];
  if (stats.views) parts.push(plural(stats.views, "view"));
  if (stats.columns !== undefined) parts.push(plural(stats.columns, "column"));
  if (stats.joins_suggested) parts.push(plural(stats.joins_suggested, "join"));
  return parts.join(" · ");
}

export function seconds(run: Pick<CollectRun, "started_at" | "finished_at" | "created_at">, now = Date.now()): number | null {
  if (!run.started_at) return null;
  const end = run.finished_at ? new Date(run.finished_at).getTime() : now;
  return Math.max(0, (end - new Date(run.started_at).getTime()) / 1000);
}

export function elapsed(total: number | null): string {
  if (total === null) return "—";
  if (total < 10) return `${total.toFixed(1)}s`;
  const s = Math.round(total);
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  return m < 60 ? `${m}m ${s % 60}s` : `${Math.floor(m / 60)}h ${m % 60}m`;
}

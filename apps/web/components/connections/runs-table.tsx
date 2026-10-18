"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { ChevronRight, History, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Table, Td, Th, Tr } from "@/components/ui/table";
import { api, type CollectRun } from "@/lib/api";
import { when } from "@/lib/format";
import { cn } from "@/lib/utils";
import { KindMark } from "./kinds";
import {
  assets, elapsed, FAILURE_TITLE, isActive, PHASE_LABEL, RunProgress, RunStatusPill, seconds, TRIGGER_LABEL,
} from "./run-ui";

export type RunFilter = "all" | "active" | "succeeded" | "failed" | "cancelled";
const FILTERS: { id: RunFilter; label: string }[] = [
  { id: "all", label: "All" }, { id: "active", label: "Running" }, { id: "succeeded", label: "Succeeded" },
  { id: "failed", label: "Failed" }, { id: "cancelled", label: "Cancelled" },
];
const PAGE = 50;

/** The run history, newest first. Refreshes every 2 seconds while anything is running. */
export function RunsTable({ connectionId, filter, onFilter, refreshKey = 0 }: {
  connectionId?: string; filter: RunFilter; onFilter: (f: RunFilter) => void; refreshKey?: number;
}) {
  const router = useRouter();
  const [runs, setRuns] = useState<CollectRun[] | null>(null);
  const [more, setMore] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [, tick] = useState(0);

  const query = useCallback((before?: string) => {
    const q = new URLSearchParams({ limit: String(PAGE) });
    if (connectionId) q.set("connection_id", connectionId);
    if (filter !== "all") q.set("status", filter);
    if (before) q.set("before", before);
    return api.get<CollectRun[]>(`/connections/runs?${q}`);
  }, [connectionId, filter]);

  const load = useCallback(() => query().then((r) => {
    // Keep any older pages already loaded; refresh only the newest page.
    setRuns((prev) => prev && prev.length > PAGE ? [...r, ...prev.filter((p) => !r.some((x) => x.id === p.id)).slice(PAGE)] : r);
    setMore((m) => m || r.length === PAGE);
  }).catch(() => setRuns((prev) => prev ?? [])), [query]);

  useEffect(() => { setRuns(null); setMore(false); load(); }, [load, refreshKey]);
  const active = runs?.some(isActive);
  useEffect(() => {
    const t = setInterval(() => { load(); tick((n) => n + 1); }, active ? 2000 : 15000);
    return () => clearInterval(t);
  }, [load, active]);

  async function loadMore() {
    if (!runs?.length) return;
    setLoadingMore(true);
    try {
      const older = await query(runs[runs.length - 1].created_at);
      setRuns([...runs, ...older]);
      setMore(older.length === PAGE);
    } finally { setLoadingMore(false); }
  }

  return (
    <Card className="overflow-hidden">
      <div className="flex flex-wrap items-center gap-1.5 border-b border-border px-4 py-3">
        {FILTERS.map((f) => (
          <button key={f.id} onClick={() => onFilter(f.id)}
            className={cn("h-7 rounded-full border px-3 text-caption font-medium transition-colors",
              filter === f.id ? "border-primary/40 bg-primary-soft text-primary" : "border-border text-muted-foreground hover:bg-muted/50 hover:text-foreground")}>
            {f.label}
          </button>
        ))}
        {active && (
          <span className="ml-auto flex items-center gap-1.5 text-caption text-muted-foreground">
            <span className="size-1.5 animate-pulse-dot rounded-full bg-primary" />Updating live
          </span>
        )}
      </div>
      {runs === null ? (
        <div className="flex items-center justify-center gap-2 py-12 text-body text-muted-foreground"><Loader2 className="size-4 animate-spin" />Loading runs…</div>
      ) : runs.length === 0 ? (
        <EmptyState icon={History} title={filter === "all" ? "No runs yet" : "No runs match"}
          description={filter === "all" ? "Each time Nexus reads a connection, the run appears here with its progress, results and log."
            : "Try another filter."} />
      ) : (
        <>
          <Table>
            <thead>
              <tr>
                <Th className="w-[130px]">Status</Th>
                {!connectionId && <Th>Source</Th>}
                <Th>Result</Th>
                <Th className="w-[140px]">Started</Th>
                <Th className="w-[100px]">Duration</Th>
                <Th className="w-[150px]">Trigger</Th>
                <Th className="w-10" />
              </tr>
            </thead>
            <tbody>
              {runs.map((r) => (
                <Tr key={r.id} className="cursor-pointer" onClick={() => router.push(`/connections/runs/${r.id}`)}>
                  <Td><RunStatusPill run={r} /></Td>
                  {!connectionId && (
                    <Td>
                      <div className="flex min-w-0 items-center gap-2.5">
                        <KindMark kind={r.connection_kind ?? ""} size="sm" />
                        <span className="truncate font-medium text-foreground">{r.connection_label}</span>
                      </div>
                    </Td>
                  )}
                  <Td className="min-w-[220px]">
                    {isActive(r) ? (
                      <div className="space-y-1.5">
                        <div className="flex items-center justify-between gap-3 text-caption">
                          <span className="text-muted-foreground">{PHASE_LABEL[r.phase]}</span>
                          <span className="num font-medium text-foreground">{Math.round(r.progress)}%</span>
                        </div>
                        <RunProgress run={r} />
                      </div>
                    ) : r.status === "failed" ? (
                      <span className="text-danger">{FAILURE_TITLE[r.error_kind ?? "warehouse"] ?? "Failed"}</span>
                    ) : r.status === "succeeded" ? (
                      <span className="text-foreground">{assets(r.stats) || "Nothing found"}</span>
                    ) : <span className="text-muted-foreground">Stopped before finishing</span>}
                  </Td>
                  <Td className="text-muted-foreground" title={new Date(r.created_at).toLocaleString()}>{when(r.created_at)}</Td>
                  <Td className="num text-muted-foreground">{elapsed(seconds(r))}</Td>
                  <Td className="text-muted-foreground">
                    <div className="truncate">{TRIGGER_LABEL[r.trigger]}</div>
                    {r.requested_by_name && <div className="truncate text-caption">{r.requested_by_name}</div>}
                  </Td>
                  <Td><ChevronRight className="size-4 text-muted-foreground" /></Td>
                </Tr>
              ))}
            </tbody>
          </Table>
          {more && (
            <div className="flex justify-center border-t border-border py-3">
              <Button variant="ghost" size="sm" disabled={loadingMore} onClick={loadMore}>
                {loadingMore && <Loader2 className="animate-spin" />}Show older runs
              </Button>
            </div>
          )}
        </>
      )}
    </Card>
  );
}

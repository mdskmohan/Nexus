"use client";

import { useEffect, useRef } from "react";
import { useToast } from "@/components/ui/toast";
import { api, ApiError, type CollectRun } from "@/lib/api";
import { assets, FAILURE_TITLE } from "./run-ui";

/**
 * Tells people when a run finishes, wherever they are in the app: a failure stays on screen with its reason
 * until dismissed. Checks every 3 seconds while runs are active, every 20 seconds otherwise.
 */
export function RunWatcher() {
  const toast = useToast();
  const active = useRef<Map<string, CollectRun> | null>(null);
  // Runs started in this tab: announced even if they finish before the next check sees them running.
  const started = useRef<Set<string>>(new Set());

  useEffect(() => {
    let stopped = false;
    let timer: ReturnType<typeof setTimeout>;
    // One check at a time; a wake-up during a check runs another right after it.
    let checking = false;
    let again = false;

    async function check() {
      if (checking) { again = true; return; }
      checking = true;
      clearTimeout(timer);
      try { await once(); } finally {
        checking = false;
        if (again && !stopped) { again = false; check(); }
      }
    }

    async function once() {
      let running: CollectRun[];
      try {
        running = await api.get<CollectRun[]>("/connections/runs?status=active&limit=200");
      } catch (e) {
        if (e instanceof ApiError && (e.status === 401 || e.status === 403)) return; // not for this person
        running = active.current ? [...active.current.values()] : [];
      }
      if (stopped) return;
      const now = new Map(running.map((r) => [r.id, r]));
      // Only runs seen running on an earlier check (or started here) are announced, so loading the page
      // announces nothing. Someone already looking at the run sees the outcome there.
      const ended = new Map<string, CollectRun | undefined>(active.current ?? []);
      for (const id of started.current) if (!ended.has(id)) ended.set(id, undefined);
      for (const [id, before] of ended) {
        if (now.has(id)) continue;
        started.current.delete(id);
        window.dispatchEvent(new CustomEvent(RUN_FINISHED, { detail: id }));
        if (window.location.pathname === `/connections/runs/${id}`) continue;
        try {
          const run = await api.get<CollectRun>(`/connections/runs/${id}`);
          const name = run.connection_label ?? before?.connection_label ?? "A connection";
          if (run.status === "succeeded") {
            toast({ tone: "success", title: `${name} read`, description: assets(run.stats) || "Nothing new found.",
              href: `/connections/runs/${id}`, action: "View run" });
          } else if (run.status === "failed") {
            toast({ tone: "danger", title: `${name}: ${FAILURE_TITLE[run.error_kind ?? "warehouse"] ?? "run failed"}`,
              description: run.hint ?? run.error, href: `/connections/runs/${id}`, action: "See what happened" });
          }
        } catch { /* the run was removed with its connection */ }
      }
      active.current = now;
      timer = setTimeout(check, now.size ? 3000 : 20000);
    }

    check();
    const wake = (e: Event) => {
      const id = (e as CustomEvent<string | undefined>).detail;
      if (id) started.current.add(id);
      check();
    };
    window.addEventListener("nexus:run-started", wake);
    return () => { stopped = true; clearTimeout(timer); window.removeEventListener("nexus:run-started", wake); };
  }, [toast]);

  return null;
}

/** Fired on window when a run the watcher was following ends; pages listen to refresh at once. */
export const RUN_FINISHED = "nexus:run-finished";

/** Call after starting a run so the watcher follows it from the start. */
export function announceRunStarted(runId: string) {
  window.dispatchEvent(new CustomEvent("nexus:run-started", { detail: runId }));
}

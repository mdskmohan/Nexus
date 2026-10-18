"use client";

import { useEffect, useRef, useState } from "react";
import { api, ApiError, type CollectRun, type RunLogLine } from "@/lib/api";

export type StreamState = "connecting" | "live" | "polling" | "ended" | "missing";

const FINISHED = new Set(["succeeded", "failed", "cancelled"]);
const POLL_MS = 1500;

/**
 * Follow a run: its state and its log, live.
 *
 * Uses server-sent events (the browser resumes after the last line it saw if the connection drops). If the
 * stream cannot be opened at all, it falls back to asking for new lines every 1.5 seconds.
 */
export function useRunStream(runId: string) {
  const [run, setRun] = useState<CollectRun | null>(null);
  const [logs, setLogs] = useState<RunLogLine[]>([]);
  const [state, setState] = useState<StreamState>("connecting");
  const last = useRef(0);

  useEffect(() => {
    let closed = false;
    let source: EventSource | null = null;
    let timer: ReturnType<typeof setTimeout> | null = null;
    last.current = 0;
    setRun(null); setLogs([]); setState("connecting");

    const append = (lines: RunLogLine[]) => {
      const fresh = lines.filter((l) => l.id > last.current);
      if (!fresh.length) return;
      last.current = fresh[fresh.length - 1].id;
      setLogs((all) => [...all, ...fresh]);
    };

    async function poll() {
      try {
        const [r, lines] = await Promise.all([
          api.get<CollectRun>(`/connections/runs/${runId}`),
          api.get<RunLogLine[]>(`/connections/runs/${runId}/logs?after=${last.current}`),
        ]);
        if (closed) return;
        setRun(r); append(lines);
        if (FINISHED.has(r.status)) { setState("ended"); return; }
        setState("polling");
      } catch (e) {
        if (closed) return;
        if (e instanceof ApiError && e.status === 404) { setState("missing"); return; }
      }
      timer = setTimeout(poll, POLL_MS);
    }

    function stream() {
      let opened = false;
      source = new EventSource(`/api/connections/runs/${runId}/events`);
      source.onopen = () => { opened = true; if (!closed) setState("live"); };
      source.addEventListener("run", (e) => { if (!closed) setRun(JSON.parse((e as MessageEvent).data)); });
      source.addEventListener("log", (e) => { if (!closed) append([JSON.parse((e as MessageEvent).data)]); });
      source.addEventListener("end", () => {
        source?.close();
        // One last read, so nothing written between the final event and the close is missed.
        if (!closed) poll().then(() => !closed && setState("ended"));
      });
      source.onerror = () => {
        // Before the stream opened: it is not available here (or the run does not exist). Poll instead.
        // After: the browser reconnects by itself and resumes after the last line.
        if (!opened || source?.readyState === EventSource.CLOSED) {
          source?.close();
          if (!closed) poll();
        }
      };
    }

    if (typeof EventSource === "undefined") poll(); else stream();
    return () => { closed = true; source?.close(); if (timer) clearTimeout(timer); };
  }, [runId]);

  return { run, logs, state };
}

"use client";

import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { AlertTriangle, ArrowDownToLine, Check, CheckCircle2, Copy, Download, Info, Terminal, XCircle } from "lucide-react";
import type { RunLogLine } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { StreamState } from "./use-run-stream";

const LEVEL = {
  info: { icon: Info, text: "text-muted-foreground", row: "" },
  success: { icon: CheckCircle2, text: "text-success", row: "" },
  warning: { icon: AlertTriangle, text: "text-warning", row: "bg-warning-soft/40" },
  error: { icon: XCircle, text: "text-danger", row: "bg-danger-soft/50" },
} as const;

const STATE_LABEL: Record<StreamState, { label: string; dot: string; pulse?: boolean }> = {
  connecting: { label: "Connecting", dot: "bg-muted-foreground", pulse: true },
  live: { label: "Live", dot: "bg-success", pulse: true },
  polling: { label: "Live (checking every 1.5s)", dot: "bg-info", pulse: true },
  ended: { label: "Finished", dot: "bg-muted-foreground" },
  missing: { label: "Not found", dot: "bg-danger" },
};

function clock(iso: string) {
  const d = new Date(iso);
  return `${d.toLocaleTimeString(undefined, { hour12: false })}.${String(d.getMilliseconds()).padStart(3, "0")}`;
}

/** The run's log as it is written: newest at the bottom, following along unless you scroll up. */
export function LogConsole({ logs, state, fileName }: { logs: RunLogLine[]; state: StreamState; fileName: string }) {
  const box = useRef<HTMLDivElement>(null);
  const [follow, setFollow] = useState(true);
  const [onlyProblems, setOnlyProblems] = useState(false);
  const [copied, setCopied] = useState(false);
  const shown = onlyProblems ? logs.filter((l) => l.level === "warning" || l.level === "error") : logs;
  const problems = logs.filter((l) => l.level === "warning" || l.level === "error").length;

  useLayoutEffect(() => {
    if (follow && box.current) box.current.scrollTop = box.current.scrollHeight;
  }, [shown.length, follow]);

  useEffect(() => {
    if (!copied) return;
    const t = setTimeout(() => setCopied(false), 1500);
    return () => clearTimeout(t);
  }, [copied]);

  const text = () => logs.map((l) => `${l.at}  ${l.level.toUpperCase().padEnd(7)}  ${l.message}`).join("\n");
  const s = STATE_LABEL[state];

  return (
    <div className="overflow-hidden rounded-lg border border-border bg-card">
      <div className="flex flex-wrap items-center gap-2 border-b border-border px-4 py-2.5">
        <Terminal className="size-4 text-muted-foreground" />
        <span className="text-body font-medium text-foreground">Log</span>
        <span className="num text-caption text-muted-foreground">{logs.length} lines</span>
        <span className="ml-1 inline-flex items-center gap-1.5 rounded-full bg-muted px-2 py-0.5 text-caption text-muted-foreground">
          <span className={cn("size-1.5 rounded-full", s.dot, s.pulse && "animate-pulse-dot")} />{s.label}
        </span>
        <div className="ml-auto flex items-center gap-1">
          <button onClick={() => setOnlyProblems(!onlyProblems)} aria-pressed={onlyProblems}
            className={cn("h-7 rounded-md px-2 text-caption font-medium transition-colors",
              onlyProblems ? "bg-warning-soft text-warning-soft-foreground" : "text-muted-foreground hover:bg-accent hover:text-foreground")}>
            Problems only{problems ? ` (${problems})` : ""}
          </button>
          <button onClick={() => setFollow(!follow)} aria-pressed={follow} title="Keep the newest line in view"
            className={cn("inline-flex h-7 items-center gap-1 rounded-md px-2 text-caption font-medium transition-colors",
              follow ? "bg-primary-soft text-primary" : "text-muted-foreground hover:bg-accent hover:text-foreground")}>
            <ArrowDownToLine className="size-3.5" />Follow
          </button>
          <button title="Copy the log" aria-label="Copy the log" onClick={() => navigator.clipboard.writeText(text()).then(() => setCopied(true))}
            className="inline-flex size-7 items-center justify-center rounded-md text-muted-foreground hover:bg-accent hover:text-foreground">
            {copied ? <Check className="size-3.5 text-success" /> : <Copy className="size-3.5" />}
          </button>
          <button title="Download the log" aria-label="Download the log" onClick={() => {
            const url = URL.createObjectURL(new Blob([text()], { type: "text/plain" }));
            const a = Object.assign(document.createElement("a"), { href: url, download: fileName });
            a.click(); URL.revokeObjectURL(url);
          }} className="inline-flex size-7 items-center justify-center rounded-md text-muted-foreground hover:bg-accent hover:text-foreground">
            <Download className="size-3.5" />
          </button>
        </div>
      </div>
      <div ref={box} role="log" aria-live="polite" aria-relevant="additions"
        onScroll={(e) => {
          const el = e.currentTarget;
          const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 24;
          if (atBottom !== follow) setFollow(atBottom);
        }}
        className="max-h-[460px] min-h-[220px] overflow-y-auto bg-muted/30 py-2 font-mono text-[12.5px] leading-relaxed">
        {shown.length === 0 ? (
          <p className="px-4 py-6 text-center font-sans text-body text-muted-foreground">
            {onlyProblems ? "No warnings or errors." : state === "connecting" ? "Connecting to the log…" : "Nothing logged yet."}
          </p>
        ) : shown.map((l) => {
          const lv = LEVEL[l.level] ?? LEVEL.info;
          const Icon = lv.icon;
          return (
            <div key={l.id} className={cn("grid grid-cols-[auto_auto_1fr] items-start gap-3 px-4 py-0.5 animate-fade-in", lv.row)}>
              <span className="num select-none text-muted-foreground/70">{clock(l.at)}</span>
              <Icon className={cn("mt-[3px] size-3.5", lv.text)} aria-label={l.level} />
              <span className={cn("whitespace-pre-wrap break-words", l.level === "error" ? "text-danger" : "text-foreground")}>{l.message}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

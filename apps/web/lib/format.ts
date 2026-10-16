import type { RunStatus } from "./api";

export function when(iso: string | null | undefined): string {
  if (!iso) return "";
  const d = new Date(iso);
  const diff = (Date.now() - d.getTime()) / 1000;
  if (diff < 60) return "just now";
  if (diff < 3600) return `${Math.floor(diff / 60)} min ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)} h ago`;
  return d.toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
}

export function duration(start: string | null, end: string | null): string {
  if (!start) return "";
  const s = Math.max(0, Math.round(((end ? new Date(end) : new Date()).getTime() - new Date(start).getTime()) / 1000));
  return s < 60 ? `${s}s` : `${Math.floor(s / 60)}m ${s % 60}s`;
}

export function money(v: string | number | undefined): string {
  return `$${Number(v ?? 0).toFixed(2)}`;
}

export const RUN_STATUS: Record<RunStatus, { label: string; tone: string }> = {
  queued: { label: "Waiting to start", tone: "pill" },
  running: { label: "Working", tone: "pill pill-brand" },
  waiting: { label: "Waiting for a person", tone: "pill pill-warn" },
  succeeded: { label: "Done", tone: "pill pill-ok" },
  failed: { label: "Did not finish", tone: "pill pill-bad" },
  cancelled: { label: "Stopped", tone: "pill" },
};

export function plural(n: number, one: string, many = `${one}s`): string {
  return `${n} ${n === 1 ? one : many}`;
}

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

export function bytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(0)} KB`;
  return `${(n / 1024 / 1024).toFixed(1)} MB`;
}

export function money(v: string | number | undefined): string {
  return `$${Number(v ?? 0).toFixed(2)}`;
}

export const RUN_STATUS: Record<RunStatus, { label: string; tone: string }> = {
  queued: { label: "Waiting to start", tone: "pill" },
  running: { label: "Working", tone: "pill pill-brand" },
  needs_review: { label: "Ready for your review", tone: "pill pill-warn" },
  approved: { label: "Approved", tone: "pill pill-ok" },
  rejected: { label: "Sent back", tone: "pill pill-bad" },
  failed: { label: "Did not finish", tone: "pill pill-bad" },
  cancelled: { label: "Stopped", tone: "pill" },
};

export function plural(n: number, one: string, many = `${one}s`): string {
  return `${n} ${n === 1 ? one : many}`;
}

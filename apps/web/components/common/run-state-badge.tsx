import { cn } from "@/lib/utils"
import type { RunState } from "@/lib/types"

const TONE: Record<RunState, string> = {
  success: "bg-run-success-soft text-run-success-soft-foreground",
  running: "bg-run-running-soft text-run-running-soft-foreground",
  failed: "bg-run-failed-soft text-run-failed-soft-foreground",
  queued: "bg-run-queued-soft text-run-queued-soft-foreground",
}

const DOT: Record<RunState, string> = {
  success: "bg-run-success",
  running: "bg-run-running animate-pulse-dot",
  failed: "bg-run-failed",
  queued: "bg-run-queued",
}

const LABEL: Record<RunState, string> = {
  success: "Succeeded",
  running: "Running",
  failed: "Failed",
  queued: "Queued",
}

export function RunStateBadge({ state, className }: { state: RunState; className?: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-sm px-1.5 py-0.5 text-caption font-medium",
        TONE[state],
        className
      )}
    >
      <span className={cn("size-1.5 rounded-full", DOT[state])} aria-hidden />
      {LABEL[state]}
    </span>
  )
}

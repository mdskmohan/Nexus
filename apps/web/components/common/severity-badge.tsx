import { cn } from "@/lib/utils"
import type { Severity } from "@/lib/types"

const TONE: Record<Severity, string> = {
  critical: "bg-severity-critical-soft text-severity-critical-soft-foreground",
  high: "bg-severity-high-soft text-severity-high-soft-foreground",
  medium: "bg-severity-medium-soft text-severity-medium-soft-foreground",
  low: "bg-severity-low-soft text-severity-low-soft-foreground",
}

const DOT: Record<Severity, string> = {
  critical: "bg-severity-critical",
  high: "bg-severity-high",
  medium: "bg-severity-medium",
  low: "bg-severity-low",
}

export function SeverityBadge({ severity, className }: { severity: Severity; className?: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-sm px-1.5 py-0.5 text-caption font-medium capitalize",
        TONE[severity],
        className
      )}
    >
      <span className={cn("size-1.5 rounded-full", DOT[severity])} aria-hidden />
      {severity}
    </span>
  )
}

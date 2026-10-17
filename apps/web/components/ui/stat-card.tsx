import * as React from "react";
import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

const tones = {
  neutral: "bg-muted text-muted-foreground",
  primary: "bg-primary-soft text-primary",
  success: "bg-success-soft text-success-soft-foreground",
  warning: "bg-warning-soft text-warning-soft-foreground",
  danger: "bg-danger-soft text-danger-soft-foreground",
  info: "bg-info-soft text-info-soft-foreground",
};

/** A KPI tile: label, a big number, a line of context. */
export function StatCard({ label, value, icon: Icon, tone = "neutral", sub, className }: {
  label: string; value: React.ReactNode; icon?: LucideIcon; tone?: keyof typeof tones; sub?: React.ReactNode; className?: string;
}) {
  return (
    <div className={cn("relative rounded-lg border border-border bg-card p-4 transition-shadow hover:shadow-sm", className)}>
      <div className="flex items-start justify-between gap-3">
        <p className="text-body text-muted-foreground">{label}</p>
        {Icon && <div className={cn("rounded-md p-1.5", tones[tone])}><Icon className="size-4" /></div>}
      </div>
      <p className="num mt-2 text-display text-foreground">{value}</p>
      {sub && <p className="mt-1 text-caption text-muted-foreground">{sub}</p>}
    </div>
  );
}

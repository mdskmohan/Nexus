import * as React from "react";
import { cn } from "@/lib/utils";

export type Tone = "success" | "warning" | "danger" | "info" | "neutral" | "primary";

const tones: Record<Tone, string> = {
  success: "bg-success-soft text-success-soft-foreground",
  warning: "bg-warning-soft text-warning-soft-foreground",
  danger: "bg-danger-soft text-danger-soft-foreground",
  info: "bg-info-soft text-info-soft-foreground",
  neutral: "bg-muted text-muted-foreground",
  primary: "bg-primary-soft text-primary",
};

const dots: Record<Tone, string> = {
  success: "bg-success", warning: "bg-warning", danger: "bg-danger", info: "bg-info",
  neutral: "bg-muted-foreground", primary: "bg-primary",
};

/** The one small chip for status, kind and role. */
export function StatusPill({ tone, icon, pulse, dot, className, children }: {
  tone: Tone; icon?: React.ReactNode; pulse?: boolean; dot?: boolean; className?: string; children: React.ReactNode;
}) {
  return (
    <span className={cn("inline-flex h-6 items-center gap-1.5 whitespace-nowrap rounded-md px-2 text-caption font-medium tracking-tight [&_svg]:size-3", tones[tone], className)}>
      {(dot || pulse) && <span className={cn("h-1.5 w-1.5 rounded-full", dots[tone], pulse && "animate-pulse-dot")} />}
      {icon}
      {children}
    </span>
  );
}

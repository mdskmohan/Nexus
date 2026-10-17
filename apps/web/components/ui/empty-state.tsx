import * as React from "react";
import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

export function EmptyState({ icon: Icon, title, description, action, className }: {
  icon: LucideIcon; title: string; description: React.ReactNode; action?: React.ReactNode; className?: string;
}) {
  return (
    <div className={cn("flex flex-col items-center justify-center gap-3 px-6 py-14 text-center", className)}>
      <div className="rounded-full bg-muted p-3">
        <Icon className="size-6 text-muted-foreground" strokeWidth={1.5} />
      </div>
      <div className="space-y-1">
        <h3 className="text-h2 text-foreground">{title}</h3>
        <div className="max-w-md text-body text-muted-foreground">{description}</div>
      </div>
      {action && <div className="mt-2">{action}</div>}
    </div>
  );
}

"use client";

import * as React from "react";
import { cn } from "@/lib/utils";

export type TabItem<T extends string> = { id: T; label: string; icon?: React.ReactNode; count?: number };

/** A segmented tab list (the selected tab sits on a raised background). */
export function Tabs<T extends string>({ tabs, value, onChange, className }: {
  tabs: TabItem<T>[]; value: T; onChange: (id: T) => void; className?: string;
}) {
  return (
    <div role="tablist" className={cn("inline-flex max-w-full items-center gap-0.5 overflow-x-auto rounded-lg bg-muted p-1 text-muted-foreground", className)}>
      {tabs.map((t) => {
        const active = t.id === value;
        return (
          <button key={t.id} role="tab" aria-selected={active} onClick={() => onChange(t.id)}
            className={cn("inline-flex h-7 items-center gap-1.5 whitespace-nowrap rounded-md px-3 text-body font-medium transition-all [&_svg]:size-3.5",
              active ? "bg-card text-foreground shadow-sm" : "hover:text-foreground")}>
            {t.icon}{t.label}
            {t.count ? <span className={cn("num rounded px-1.5 text-caption", active ? "bg-primary-soft text-primary" : "bg-background/60")}>{t.count}</span> : null}
          </button>
        );
      })}
    </div>
  );
}

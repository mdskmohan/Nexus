import { cn } from "@/lib/utils";

/** The Nexus mark: a hub joined to three nodes, the knowledge graph in miniature. */
export function LogoMark({ className }: { className?: string }) {
  return (
    <span className={cn("inline-flex size-7 shrink-0 items-center justify-center rounded-md bg-gradient-to-br from-primary to-[hsl(262_83%_62%)] text-primary-foreground shadow-sm", className)}>
      <svg viewBox="0 0 24 24" className="size-[64%]" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden>
        <path d="M12 12 12 4.5M12 12l6.5 3.75M12 12l-6.5 3.75" opacity="0.8" />
        <circle cx="12" cy="4.5" r="2.3" fill="currentColor" stroke="none" />
        <circle cx="18.5" cy="15.75" r="2.3" fill="currentColor" stroke="none" />
        <circle cx="5.5" cy="15.75" r="2.3" fill="currentColor" stroke="none" />
        <circle cx="12" cy="12" r="3" fill="currentColor" stroke="none" />
      </svg>
    </span>
  );
}

export function Logo({ collapsed }: { collapsed?: boolean }) {
  return (
    <span className="flex min-w-0 items-center gap-2.5">
      <LogoMark />
      {!collapsed && <span className="truncate text-h2 tracking-tight text-foreground">Nexus</span>}
    </span>
  );
}

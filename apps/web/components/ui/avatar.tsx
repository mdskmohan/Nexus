import { cn, initials } from "@/lib/utils";

export function Avatar({ name, className }: { name: string; className?: string }) {
  return (
    <span className={cn("inline-flex size-7 shrink-0 items-center justify-center rounded-full bg-primary-soft text-caption font-semibold text-primary", className)}>
      {initials(name)}
    </span>
  );
}

import * as React from "react";
import { cn } from "@/lib/utils";

const control =
  "w-full rounded-md border border-input bg-card px-3 text-body text-foreground shadow-sm transition-colors placeholder:text-muted-foreground/70 focus-visible:border-ring focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50";

export function Input({ className, ...props }: React.InputHTMLAttributes<HTMLInputElement>) {
  return <input className={cn(control, "h-9", className)} {...props} />;
}

export function Textarea({ className, ...props }: React.TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea className={cn(control, "min-h-[72px] py-2", className)} {...props} />;
}

export function Select({ className, ...props }: React.SelectHTMLAttributes<HTMLSelectElement>) {
  return <select className={cn(control, props.multiple ? "py-1" : "h-9 pr-8", className)} {...props} />;
}

/** A labelled form field: label, control, optional hint. */
export function Field({ label, hint, optional, children, className }: {
  label: React.ReactNode; hint?: React.ReactNode; optional?: boolean; children: React.ReactNode; className?: string;
}) {
  return (
    <label className={cn("flex flex-col gap-1.5", className)}>
      <span className="text-body font-medium text-foreground">
        {label}{optional && <span className="ml-1 font-normal text-muted-foreground">(optional)</span>}
      </span>
      {children}
      {hint && <span className="text-caption text-muted-foreground">{hint}</span>}
    </label>
  );
}

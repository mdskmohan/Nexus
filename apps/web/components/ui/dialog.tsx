"use client";

import * as React from "react";
import { X } from "lucide-react";

/** A modal built on the native <dialog>: focus trapping and Escape come for free. */
export const Dialog = React.forwardRef<HTMLDialogElement, {
  title: string; description?: React.ReactNode; children: React.ReactNode; wide?: boolean;
}>(function Dialog({ title, description, children, wide }, ref) {
  return (
    <dialog ref={ref} style={wide ? { width: "min(720px, calc(100vw - 32px))" } : undefined}
      onClick={(e) => { if (e.target === e.currentTarget) e.currentTarget.close(); }}>
      <div className="flex items-start justify-between gap-4 border-b border-border px-5 py-4">
        <div>
          <h2 className="text-h2 text-foreground">{title}</h2>
          {description && <p className="mt-0.5 text-body text-muted-foreground">{description}</p>}
        </div>
        <button type="button" aria-label="Close" className="rounded-md p-1 text-muted-foreground hover:bg-accent hover:text-foreground"
          onClick={(e) => (e.currentTarget.closest("dialog") as HTMLDialogElement).close()}>
          <X className="size-4" />
        </button>
      </div>
      <div className="p-5">{children}</div>
    </dialog>
  );
});

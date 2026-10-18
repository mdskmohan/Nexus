"use client";

import * as React from "react";
import { ArrowLeft, X } from "lucide-react";

/** A panel that slides in from the right, built on the native <dialog> like Dialog. */
export const Sheet = React.forwardRef<HTMLDialogElement, {
  title: React.ReactNode; description?: React.ReactNode; children: React.ReactNode;
  footer?: React.ReactNode; onBack?: () => void;
}>(function Sheet({ title, description, children, footer, onBack }, ref) {
  return (
    <dialog ref={ref} className="sheet" onClick={(e) => { if (e.target === e.currentTarget) e.currentTarget.close(); }}>
      <div className="flex h-full flex-col">
        <div className="flex items-start gap-3 border-b border-border px-6 py-4">
          {onBack && (
            <button type="button" aria-label="Back" onClick={onBack}
              className="-ml-1 mt-0.5 rounded-md p-1 text-muted-foreground hover:bg-accent hover:text-foreground">
              <ArrowLeft className="size-4" />
            </button>
          )}
          <div className="min-w-0 flex-1">
            <h2 className="text-h2 text-foreground">{title}</h2>
            {description && <p className="mt-0.5 text-body text-muted-foreground">{description}</p>}
          </div>
          <button type="button" aria-label="Close" className="rounded-md p-1 text-muted-foreground hover:bg-accent hover:text-foreground"
            onClick={(e) => (e.currentTarget.closest("dialog") as HTMLDialogElement).close()}>
            <X className="size-4" />
          </button>
        </div>
        <div className="flex-1 overflow-y-auto px-6 py-5">{children}</div>
        {footer && <div className="flex justify-end gap-2 border-t border-border bg-muted/30 px-6 py-3">{footer}</div>}
      </div>
    </dialog>
  );
});

import * as React from "react";

export function PageHeader({ title, description, meta, actions }: {
  title: string; description?: React.ReactNode; meta?: React.ReactNode; actions?: React.ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-start justify-between gap-4">
      <div className="min-w-0 space-y-1">
        <h1 className="text-h1 tracking-tight text-foreground">{title}</h1>
        {description && <p className="text-body text-muted-foreground">{description}</p>}
        {meta && <div className="pt-0.5 text-caption text-muted-foreground">{meta}</div>}
      </div>
      {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
    </div>
  );
}

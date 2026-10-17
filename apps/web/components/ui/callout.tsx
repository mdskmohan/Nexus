import * as React from "react";
import { AlertTriangle, CheckCircle2, Info, XCircle } from "lucide-react";
import { cn } from "@/lib/utils";

const styles = {
  info: { box: "border-info/30 bg-info-soft text-info-soft-foreground", Icon: Info },
  success: { box: "border-success/30 bg-success-soft text-success-soft-foreground", Icon: CheckCircle2 },
  warning: { box: "border-warning/30 bg-warning-soft text-warning-soft-foreground", Icon: AlertTriangle },
  danger: { box: "border-danger/30 bg-danger-soft text-danger-soft-foreground", Icon: XCircle },
};

export function Callout({ tone = "info", title, children, action, className }: {
  tone?: keyof typeof styles; title?: React.ReactNode; children?: React.ReactNode; action?: React.ReactNode; className?: string;
}) {
  const { box, Icon } = styles[tone];
  return (
    <div role={tone === "danger" ? "alert" : "status"} className={cn("flex items-start gap-2.5 rounded-md border px-3.5 py-2.5 text-body", box, className)}>
      <Icon className="mt-0.5 size-4 shrink-0" />
      <div className="min-w-0 flex-1">
        {title && <p className="font-medium">{title}</p>}
        {children && <div className={cn(title && "mt-0.5 opacity-90")}>{children}</div>}
      </div>
      {action}
    </div>
  );
}

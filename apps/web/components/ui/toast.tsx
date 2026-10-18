"use client";

import Link from "next/link";
import * as React from "react";
import { AlertTriangle, CheckCircle2, Info, X, XCircle } from "lucide-react";
import { cn } from "@/lib/utils";

type Tone = "success" | "danger" | "warning" | "info";
export type Toast = { title: string; description?: React.ReactNode; tone?: Tone; href?: string; action?: string };
type Shown = Toast & { id: number };

const ToastContext = React.createContext<(t: Toast) => void>(() => {});

const STYLE: Record<Tone, { icon: typeof Info; accent: string }> = {
  success: { icon: CheckCircle2, accent: "text-success" },
  danger: { icon: XCircle, accent: "text-danger" },
  warning: { icon: AlertTriangle, accent: "text-warning" },
  info: { icon: Info, accent: "text-info" },
};
// Failures stay until someone reads them; good news goes by itself.
const LINGER: Record<Tone, number | null> = { success: 6000, info: 6000, warning: 10000, danger: null };

export function useToast() {
  return React.useContext(ToastContext);
}

export function Toaster({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = React.useState<Shown[]>([]);
  const next = React.useRef(0);
  const dismiss = React.useCallback((id: number) => setToasts((all) => all.filter((t) => t.id !== id)), []);
  const show = React.useCallback((t: Toast) => {
    const id = ++next.current;
    setToasts((all) => [...all.slice(-3), { ...t, id }]);
    const linger = LINGER[t.tone ?? "info"];
    if (linger) setTimeout(() => dismiss(id), linger);
  }, [dismiss]);

  return (
    <ToastContext.Provider value={show}>
      {children}
      <div aria-live="polite" className="pointer-events-none fixed bottom-4 right-4 z-[60] flex w-[min(380px,calc(100vw-32px))] flex-col gap-2">
        {toasts.map((t) => {
          const { icon: Icon, accent } = STYLE[t.tone ?? "info"];
          return (
            <div key={t.id} role={t.tone === "danger" ? "alert" : "status"}
              className="pointer-events-auto flex animate-fade-in items-start gap-3 rounded-lg border border-border bg-popover p-3.5 shadow-lg">
              <Icon className={cn("mt-0.5 size-4 shrink-0", accent)} />
              <div className="min-w-0 flex-1">
                <p className="text-body font-medium text-foreground">{t.title}</p>
                {t.description && <div className="mt-0.5 text-caption text-muted-foreground">{t.description}</div>}
                {t.href && (
                  <Link href={t.href} onClick={() => dismiss(t.id)} className="mt-1.5 inline-block text-caption font-medium text-primary hover:underline">
                    {t.action ?? "View"}
                  </Link>
                )}
              </div>
              <button aria-label="Dismiss" onClick={() => dismiss(t.id)} className="rounded p-0.5 text-muted-foreground hover:bg-accent hover:text-foreground">
                <X className="size-3.5" />
              </button>
            </div>
          );
        })}
      </div>
    </ToastContext.Provider>
  );
}

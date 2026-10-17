import { LogoMark } from "@/components/logo";

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="relative flex min-h-screen flex-col items-center justify-center px-4 py-12">
      <div aria-hidden className="pointer-events-none absolute inset-0 opacity-60 [background:radial-gradient(ellipse_at_top,hsl(var(--primary-soft))_0%,transparent_60%)]" />
      <div className="relative mb-8 flex items-center gap-2.5">
        <LogoMark className="size-8" />
        <span className="text-h1 tracking-tight text-foreground">Nexus</span>
      </div>
      <div className="relative w-full max-w-sm rounded-lg border border-border bg-card p-8 shadow-sm">{children}</div>
      <p className="relative mt-6 text-caption text-muted-foreground">
        Agent Studio for data teams. People in the loop, every number checked.
      </p>
    </div>
  );
}

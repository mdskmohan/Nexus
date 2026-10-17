"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { ArrowRight, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Callout } from "@/components/ui/callout";
import { Field, Input } from "@/components/ui/form";
import { api } from "@/lib/api";

export default function SignIn() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await api.post("/auth/login", { email, password });
      router.replace("/");
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="space-y-1">
        <h1 className="text-h1 text-foreground">Sign in</h1>
        <p className="text-body text-muted-foreground">Welcome back to your workspace.</p>
      </div>
      <form className="space-y-4" onSubmit={submit}>
        <Field label="Email"><Input type="email" required autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@company.com" /></Field>
        <Field label="Password"><Input type="password" required autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} /></Field>
        {error && <Callout tone="danger">{error}</Callout>}
        <Button className="w-full" disabled={busy}>
          {busy ? <><Loader2 className="animate-spin" /> Signing in…</> : <>Sign in <ArrowRight /></>}
        </Button>
      </form>
      <p className="text-center text-caption text-muted-foreground">
        New here? <Link href="/signup" className="font-medium text-primary hover:underline">Create a workspace</Link>
      </p>
    </div>
  );
}

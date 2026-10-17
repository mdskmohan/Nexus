"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { ArrowRight, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Callout } from "@/components/ui/callout";
import { Field, Input } from "@/components/ui/form";
import { api } from "@/lib/api";

export default function SignUp() {
  const router = useRouter();
  const [form, setForm] = useState({ workspace_name: "", name: "", email: "", password: "" });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) => setForm({ ...form, [k]: e.target.value });

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await api.post("/auth/signup", form);
      router.replace("/");
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="space-y-1">
        <h1 className="text-h1 text-foreground">Set up your workspace</h1>
        <p className="text-body text-muted-foreground">You will be its administrator. Add colleagues afterwards.</p>
      </div>
      <form className="space-y-4" onSubmit={submit}>
        <Field label="Workspace name"><Input required value={form.workspace_name} onChange={set("workspace_name")} placeholder="Acme Analytics" /></Field>
        <Field label="Your name"><Input required autoComplete="name" value={form.name} onChange={set("name")} /></Field>
        <Field label="Work email"><Input type="email" required autoComplete="email" value={form.email} onChange={set("email")} placeholder="you@company.com" /></Field>
        <Field label="Password" hint="At least 10 characters.">
          <Input type="password" required minLength={10} autoComplete="new-password" value={form.password} onChange={set("password")} />
        </Field>
        {error && <Callout tone="danger">{error}</Callout>}
        <Button className="w-full" disabled={busy}>
          {busy ? <><Loader2 className="animate-spin" /> Setting up…</> : <>Create workspace <ArrowRight /></>}
        </Button>
      </form>
      <p className="text-center text-caption text-muted-foreground">
        Already have an account? <Link href="/signin" className="font-medium text-primary hover:underline">Sign in</Link>
      </p>
    </div>
  );
}

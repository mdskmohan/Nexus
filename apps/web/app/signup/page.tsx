"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
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
    <main className="auth">
      <div className="card card-pad stack">
        <div className="brand" style={{ padding: 0 }}>
          <div className="brand-mark">N</div>
          <span className="brand-name">Nexus</span>
        </div>
        <div>
          <h1 style={{ fontSize: 24 }}>Set up your workspace</h1>
          <p className="muted">You will be the workspace&apos;s administrator. You can add colleagues afterwards.</p>
        </div>
        <form className="stack" onSubmit={submit}>
          <label>Workspace name<input required value={form.workspace_name} onChange={set("workspace_name")} placeholder="e.g. Acme Analytics" /></label>
          <label>Your name<input required autoComplete="name" value={form.name} onChange={set("name")} /></label>
          <label>Work email<input type="email" required autoComplete="email" value={form.email} onChange={set("email")} /></label>
          <label>
            Password <span className="hint">At least 10 characters.</span>
            <input type="password" required minLength={10} autoComplete="new-password" value={form.password} onChange={set("password")} />
          </label>
          {error && <div className="notice notice-bad"><p>{error}</p></div>}
          <button className="btn-primary" disabled={busy}>{busy ? "Setting up…" : "Create workspace account"}</button>
        </form>
        <p className="faint">Already have an account? <Link href="/signin">Sign in</Link></p>
      </div>
    </main>
  );
}

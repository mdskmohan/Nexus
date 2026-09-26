"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
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
    <main className="auth">
      <div className="card card-pad stack">
        <div className="brand" style={{ padding: 0 }}>
          <div className="brand-mark">N</div>
          <span className="brand-name">Nexus</span>
        </div>
        <div>
          <h1 style={{ fontSize: 24 }}>Sign in</h1>
          <p className="muted">Your firm&apos;s AI legal assistant.</p>
        </div>
        <form className="stack" onSubmit={submit}>
          <label>Email<input type="email" required autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} /></label>
          <label>Password<input type="password" required autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} /></label>
          {error && <div className="notice notice-bad"><p>{error}</p></div>}
          <button className="btn-primary" disabled={busy}>{busy ? "Signing in…" : "Sign in"}</button>
        </form>
        <p className="faint">New firm? <Link href="/signup">Create an account</Link></p>
      </div>
    </main>
  );
}

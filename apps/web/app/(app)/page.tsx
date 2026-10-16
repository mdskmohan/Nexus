"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api, can, type HumanRequest } from "@/lib/api";
import { when } from "@/lib/format";
import { useMe } from "@/lib/me";

// What the workspace can do today, and what is coming (see docs/build-plan.md).
const COMING = [
  { title: "Agent Studio", body: "Build agents on a visual canvas, test them step by step, and publish them to your team." },
];

export default function Home() {
  const me = useMe();
  const [requests, setRequests] = useState<HumanRequest[] | null>(null);
  const [notes, setNotes] = useState<Record<string, string>>({});
  const [error, setError] = useState("");

  const load = () => api.get<HumanRequest[]>("/requests").then(setRequests);
  useEffect(() => { load(); }, []);

  async function decide(q: HumanRequest, decision: string) {
    setError("");
    try {
      const text = notes[q.id] ?? "";
      await api.post(`/requests/${q.id}/decide`, q.kind === "clarification"
        ? { decision: "answered", answer: text }
        : { decision, note: text });
      load();
    } catch (err) { setError((err as Error).message); }
  }

  return (
    <div className="stack" style={{ gap: 28 }}>
      <div className="page-head" style={{ marginBottom: 0 }}>
        <div><h1>{me.workspace.name}</h1><p>Signed in as {me.user.name} ({me.user.role}).</p></div>
      </div>

      <section className="stack">
        <div>
          <h2>Waiting for you</h2>
          <p className="muted">Runs pause here when they need a person to approve a step or answer a question.</p>
        </div>
        {error && <div className="notice notice-bad"><p>{error}</p></div>}
        {requests === null ? <div className="empty">Loading…</div> : requests.length === 0 ? (
          <div className="card card-pad"><p className="muted">Nothing is waiting for you.</p></div>
        ) : requests.map((q) => (
          <div key={q.id} className="card card-pad stack">
            <div className="row" style={{ justifyContent: "space-between" }}>
              <div>
                <div style={{ fontWeight: 600 }}>{q.title}</div>
                <div className="faint">{q.run_title}{q.requested_for_name ? ` · started by ${q.requested_for_name}` : ""} · {when(q.created_at)}</div>
              </div>
              <span className="pill pill-warn">{q.kind === "approval" ? "Approval" : "Question"}</span>
            </div>
            {Object.keys(q.shown).length > 0 && (
              <pre style={{ whiteSpace: "pre-wrap", margin: 0 }}>{JSON.stringify(q.shown, null, 2)}</pre>
            )}
            <label>{q.kind === "approval" ? "Note (optional)" : "Your answer"}
              <textarea rows={2} value={notes[q.id] ?? ""} onChange={(e) => setNotes({ ...notes, [q.id]: e.target.value })} />
            </label>
            <div className="row" style={{ justifyContent: "flex-end" }}>
              {q.kind === "approval" ? (
                <>
                  <button className="btn-quiet" onClick={() => decide(q, "rejected")}>Reject</button>
                  <button className="btn-primary" onClick={() => decide(q, "approved")}>Approve</button>
                </>
              ) : <button className="btn-primary" onClick={() => decide(q, "answered")}>Answer</button>}
            </div>
          </div>
        ))}
      </section>

      <section className="stack">
        <div><h2>Getting started</h2></div>
        <div className="card card-pad stack" style={{ gap: 10 }}>
          <p>
            <span className={me.model_configured ? "pill pill-ok" : "pill pill-warn"}>
              {me.model_configured ? "Done" : "To do"}
            </span>{" "}
            <strong>Connect an AI model.</strong>{" "}
            {can(me, "manage_ai") ? <Link href="/settings">Workspace settings → AI models</Link> : "Ask an administrator."}
          </p>
          <p><strong>Invite your team</strong> and give each person a role. {can(me, "manage_people") && <Link href="/settings">Workspace settings → Team</Link>}</p>
          <p><strong>Connect your warehouses</strong> so Nexus can read their tables and columns. {can(me, "manage_connections") && <Link href="/connections">Connections</Link>}</p>
          <p><strong>Review the knowledge graph.</strong> A steward approves tables, joins and metrics before agents use them. <Link href="/knowledge">Knowledge graph</Link></p>
        </div>
      </section>

      <section className="stack">
        <div><h2>Coming next</h2></div>
        <div className="stack" style={{ gap: 10 }}>
          {COMING.map((c) => (
            <div key={c.title} className="card card-pad">
              <div style={{ fontWeight: 600 }}>{c.title}</div>
              <p className="muted">{c.body}</p>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}

"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api, atLeast, type DocFlags, type Run } from "@/lib/api";
import { money, plural, RUN_STATUS, when } from "@/lib/format";
import { useMe } from "@/lib/me";

type Activity = {
  metrics: Record<string, number>;
  runs: (Run & { matter_name: string })[];
  flagged_documents: { id: string; filename: string; matter_id: string; matter_name: string; flags: DocFlags }[];
  limits: { max_steps: number; budget_usd: number };
};
type AuditEvent = { id: number; action: string; target_type: string; actor_name: string | null; at: string; detail: Record<string, unknown> };

const PROTECTIONS = [
  ["Every quote is checked", "Each statement the AI makes must quote the document it relies on. Nexus checks every quote word for word before you see the answer. Anything that does not match is sent back to the AI to fix, and removed if it still does not match."],
  ["Client files stay separate", "The AI can only read the documents in the matter you are working in. The database itself blocks one firm's data from another's, so this does not depend on the AI behaving."],
  ["Documents cannot give the AI orders", "Text inside a document that tries to instruct the AI is treated as evidence, never followed, and flagged to you when the document is uploaded."],
  ["Sensitive numbers are flagged", "Uploads are scanned for identity and payment numbers (for example social security, PAN, Aadhaar, card and bank numbers) so you can check they belong in the file."],
  ["A lawyer signs off", "Everything the AI produces is a draft until an associate, partner or admin approves it. Who approved what, and when, is recorded permanently."],
  ["Limits on every task", "Each AI task has a cap on steps and on spending, so a task cannot run away."],
  ["A permanent record", "Uploads, downloads, AI tasks, approvals and settings changes are written to an audit trail that cannot be edited or deleted, even by administrators."],
];

const ACTIONS: Record<string, string> = {
  "firm.created": "Created the firm account", "user.signed_in": "Signed in", "user.added": "Added a team member",
  "user.updated": "Changed a team member", "matter.created": "Created a matter", "matter.updated": "Updated a matter",
  "document.uploaded": "Uploaded a document", "document.processed": "Document processed", "document.downloaded": "Downloaded a document",
  "document.deleted": "Removed a document", "run.started": "Started an AI task", "run.completed": "AI task finished",
  "run.approved": "Approved AI work", "run.rejected": "Sent AI work back", "file.downloaded": "Downloaded a file",
  "playbook.updated": "Edited a playbook", "playbook.approved": "Approved a playbook", "firm.updated": "Changed firm settings",
};

export default function Safety() {
  const me = useMe();
  const router = useRouter();
  const [data, setData] = useState<Activity | null>(null);
  const [audit, setAudit] = useState<AuditEvent[] | null>(null);

  useEffect(() => {
    api.get<Activity>("/activity").then(setData);
    if (atLeast(me.user.role, "partner")) api.get<AuditEvent[]>("/audit").then(setAudit);
  }, [me.user.role]);

  if (!data) return <div className="empty">Loading…</div>;
  const m = data.metrics;

  return (
    <div className="stack" style={{ gap: 28 }}>
      <div className="page-head" style={{ marginBottom: 0 }}>
        <div>
          <h1>Safety &amp; activity</h1>
          <p>What the AI has done for your firm in the last 30 days, and the protections around it.</p>
        </div>
      </div>

      <div className="grid-tiles">
        <div className="card tile"><div className="num">{m.runs}</div><div className="label">AI tasks</div></div>
        <div className="card tile"><div className="num">{m.citations_verified}</div><div className="label">Quotes checked word for word</div></div>
        <div className="card tile"><div className="num">{m.statements_removed}</div><div className="label">Unverifiable statements removed</div></div>
        <div className="card tile"><div className="num">{m.awaiting_review}</div><div className="label">Waiting for a lawyer&apos;s review</div></div>
        <div className="card tile"><div className="num">{m.with_hidden_instructions}</div><div className="label">Documents with text aimed at AI</div></div>
        <div className="card tile"><div className="num">{money(m.cost_usd)}</div><div className="label">AI cost</div></div>
      </div>

      <section className="stack">
        <h2>How your work is protected</h2>
        <div className="grid-tiles" style={{ gridTemplateColumns: "repeat(auto-fill, minmax(300px, 1fr))" }}>
          {PROTECTIONS.map(([title, body]) => (
            <div key={title} className="card card-pad stack" style={{ gap: 6 }}>
              <h3><span style={{ color: "var(--ok)" }}>✓</span> {title}</h3>
              <p className="muted">{body}</p>
            </div>
          ))}
        </div>
        <p className="faint">Current limits: {data.limits.max_steps} steps and {money(data.limits.budget_usd)} per task.</p>
      </section>

      {data.flagged_documents.length > 0 && (
        <section className="stack">
          <h2>Documents that need a look</h2>
          <div className="card">
            <table>
              <thead><tr><th>Document</th><th>Why</th></tr></thead>
              <tbody>
                {data.flagged_documents.map((d) => (
                  <tr key={d.id}>
                    <td><Link href={`/matters/${d.matter_id}`} style={{ fontWeight: 600 }}>{d.filename}</Link><div className="faint">{d.matter_name}</div></td>
                    <td className="muted">
                      {!!d.flags.hidden_instruction_count && <div>Contains text aimed at an AI ({plural(d.flags.hidden_instruction_count, "place")})</div>}
                      {Object.entries(d.flags.sensitive ?? {}).map(([k, n]) => <div key={k}>{plural(n, k)}</div>)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      <section className="stack">
        <h2>Recent AI tasks</h2>
        <div className="card">
          {data.runs.length === 0 ? <div className="empty">No AI tasks yet.</div> : (
            <table>
              <thead><tr><th>Task</th><th>Status</th><th>Cost</th><th>When</th></tr></thead>
              <tbody>
                {data.runs.map((r) => (
                  <tr key={r.id} className="link-row" onClick={() => router.push(`/tasks/${r.id}`)}>
                    <td><div style={{ fontWeight: 600 }}>{r.title}</div><div className="faint">{r.matter_name}</div></td>
                    <td><span className={RUN_STATUS[r.status].tone}>{RUN_STATUS[r.status].label}</span></td>
                    <td className="muted">{money(r.cost_usd)}</td>
                    <td className="muted">{when(r.created_at)}{r.created_by_name ? ` · ${r.created_by_name}` : ""}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </section>

      {audit && (
        <section className="stack">
          <div>
            <h2>Audit trail</h2>
            <p className="muted">Permanent record. It cannot be edited or deleted.</p>
          </div>
          <div className="card">
            <table>
              <thead><tr><th>When</th><th>Who</th><th>What</th></tr></thead>
              <tbody>
                {audit.slice(0, 100).map((e) => (
                  <tr key={e.id}>
                    <td className="muted" style={{ whiteSpace: "nowrap" }}>{new Date(e.at).toLocaleString()}</td>
                    <td>{e.actor_name ?? "Nexus"}</td>
                    <td>{ACTIONS[e.action] ?? e.action}{typeof e.detail?.filename === "string" ? `: ${e.detail.filename}` : ""}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </div>
  );
}

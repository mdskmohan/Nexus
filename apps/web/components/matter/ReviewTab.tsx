"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api, type Doc, type Playbook } from "@/lib/api";
import ModelPicker from "@/components/ModelPicker";

const ROLES = [
  "We act for the disclosing party (our client shares the information)",
  "We act for the receiving party (our client receives the information)",
  "Mutual: our client both shares and receives information",
  "We act for the customer",
  "We act for the supplier",
];

export default function ReviewTab({ matterId, readyDocs, onGoToDocuments }: {
  matterId: string; readyDocs: Doc[]; onGoToDocuments: () => void;
}) {
  const router = useRouter();
  const [playbooks, setPlaybooks] = useState<Playbook[]>([]);
  const [form, setForm] = useState({ document_id: "", playbook_id: "", client_role: ROLES[2], instructions: "", model_id: "" });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.get<Playbook[]>("/playbooks").then((p) => {
      setPlaybooks(p);
      setForm((f) => ({ ...f, playbook_id: f.playbook_id || p[0]?.id || "" }));
    });
  }, []);
  useEffect(() => {
    setForm((f) => ({ ...f, document_id: f.document_id || readyDocs[0]?.id || "" }));
  }, [readyDocs]);

  async function start(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const { id } = await api.post<{ id: string }>(`/matters/${matterId}/reviews`, { ...form, model_id: form.model_id || null });
      router.push(`/tasks/${id}`);
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  }

  if (!readyDocs.length) {
    return (
      <div className="card empty stack" style={{ alignItems: "center" }}>
        <h2>Add the contract first</h2>
        <p>Upload the contract to this matter, then come back to review it.</p>
        <button className="btn-primary" onClick={onGoToDocuments}>Add documents</button>
      </div>
    );
  }

  const playbook = playbooks.find((p) => p.id === form.playbook_id);
  const doc = readyDocs.find((d) => d.id === form.document_id);

  return (
    <div className="grid-2">
      <form className="card card-pad stack" onSubmit={start}>
        <label>
          Contract to review
          <select value={form.document_id} onChange={(e) => setForm({ ...form, document_id: e.target.value })}>
            {readyDocs.map((d) => <option key={d.id} value={d.id}>{d.filename}</option>)}
          </select>
        </label>
        <label>
          Review against
          <select value={form.playbook_id} onChange={(e) => setForm({ ...form, playbook_id: e.target.value })}>
            {playbooks.map((p) => <option key={p.id} value={p.id}>{p.name} ({p.position_count} points)</option>)}
          </select>
        </label>
        {playbook && !playbook.validated_by && (
          <div className="notice notice-warn" style={{ padding: "8px 12px" }}>
            <p>This is a starter playbook that no lawyer at your firm has approved yet. <Link href={`/playbooks/${playbook.id}`}>Review and approve it</Link>.</p>
          </div>
        )}
        <label>
          Who do we act for?
          <select value={ROLES.includes(form.client_role) ? form.client_role : "other"} onChange={(e) => setForm({ ...form, client_role: e.target.value === "other" ? "" : e.target.value })}>
            {ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
            <option value="other">Something else…</option>
          </select>
          {!ROLES.includes(form.client_role) && (
            <input required placeholder="Describe our client's role" value={form.client_role} onChange={(e) => setForm({ ...form, client_role: e.target.value })} />
          )}
        </label>
        <label>
          Anything else the reviewer should know? <span className="hint">Optional. For example: &ldquo;Client will accept a 3-year term&rdquo;.</span>
          <textarea rows={3} value={form.instructions} onChange={(e) => setForm({ ...form, instructions: e.target.value })} />
        </label>
        <ModelPicker value={form.model_id} onChange={(id) => setForm((f) => ({ ...f, model_id: id }))} />
        {error && <div className="notice notice-bad"><p>{error}</p></div>}
        <div className="row"><button className="btn-primary" disabled={busy || !form.document_id || !form.playbook_id}>{busy ? "Starting…" : "Start review"}</button></div>
      </form>
      <div className="card card-pad stack" style={{ gap: 10 }}>
        <h3>What you will get</h3>
        <p className="muted">A finding for every point in the playbook: meets the standard, deviates, missing, or needs your judgement, each quoting the clause it relies on.</p>
        <p className="muted">Suggested wording for every gap, a short summary, and a draft note to the client.</p>
        <p className="muted">
          A review memo in Word{doc?.content_type.includes("wordprocessingml") ? ", and a copy of the contract with the suggested changes as tracked changes you can accept or reject in Word" : ""}.
        </p>
      </div>
    </div>
  );
}

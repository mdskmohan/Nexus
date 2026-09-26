"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { api, type Matter } from "@/lib/api";
import { plural, when } from "@/lib/format";

export default function Matters() {
  const router = useRouter();
  const [matters, setMatters] = useState<Matter[] | null>(null);
  const [filter, setFilter] = useState("");
  const dialog = useRef<HTMLDialogElement>(null);
  const [form, setForm] = useState({ name: "", client_name: "", description: "" });
  const [error, setError] = useState("");

  useEffect(() => {
    api.get<Matter[]>("/matters").then(setMatters);
  }, []);

  async function create(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    try {
      const { id } = await api.post<{ id: string }>("/matters", form);
      router.push(`/matters/${id}`);
    } catch (err) {
      setError((err as Error).message);
    }
  }

  const shown = (matters ?? []).filter((m) =>
    `${m.name} ${m.client_name}`.toLowerCase().includes(filter.toLowerCase()),
  );

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Matters</h1>
          <p>Each matter keeps its documents, questions and reviews together, separate from every other matter.</p>
        </div>
        <button className="btn-primary" onClick={() => dialog.current?.showModal()}>New matter</button>
      </div>

      {matters && matters.length > 0 && (
        <input placeholder="Find a matter or client…" value={filter} onChange={(e) => setFilter(e.target.value)}
               style={{ maxWidth: 360, marginBottom: 16 }} />
      )}

      <div className="card">
        {matters === null ? (
          <div className="empty">Loading…</div>
        ) : matters.length === 0 ? (
          <div className="empty stack" style={{ alignItems: "center" }}>
            <h2>No matters yet</h2>
            <p>Create a matter, add its documents, then ask questions or review a contract.</p>
            <button className="btn-primary" onClick={() => dialog.current?.showModal()}>Create your first matter</button>
          </div>
        ) : (
          <table>
            <thead>
              <tr><th>Matter</th><th>Documents</th><th>AI tasks</th><th>Last activity</th></tr>
            </thead>
            <tbody>
              {shown.map((m) => (
                <tr key={m.id} className="link-row" onClick={() => router.push(`/matters/${m.id}`)}>
                  <td>
                    <div style={{ fontWeight: 600 }}>{m.name}</div>
                    <div className="faint">{m.client_name || "No client set"}{m.status === "closed" ? " · Closed" : ""}</div>
                  </td>
                  <td>{m.documents}</td>
                  <td>
                    {m.tasks}
                    {!!m.awaiting_review && <span className="pill pill-warn" style={{ marginLeft: 8 }}>{plural(m.awaiting_review, "to review", "to review")}</span>}
                  </td>
                  <td className="muted">{when(m.last_activity)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <dialog ref={dialog}>
        <form className="card-pad stack" onSubmit={create}>
          <h2>New matter</h2>
          <label>Matter name<input required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="e.g. Acme / Brightline collaboration" /></label>
          <label>Client<input value={form.client_name} onChange={(e) => setForm({ ...form, client_name: e.target.value })} /></label>
          <label>
            What is this matter about? <span className="hint">Optional. The AI uses this as background.</span>
            <textarea value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
          </label>
          {error && <div className="notice notice-bad"><p>{error}</p></div>}
          <div className="row" style={{ justifyContent: "flex-end" }}>
            <button type="button" className="btn-quiet" onClick={() => dialog.current?.close()}>Cancel</button>
            <button className="btn-primary">Create matter</button>
          </div>
        </form>
      </dialog>
    </>
  );
}

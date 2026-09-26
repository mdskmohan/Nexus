"use client";

import Link from "next/link";
import { use, useCallback, useEffect, useState } from "react";
import { api, atLeast, type Playbook, type Position } from "@/lib/api";
import { when } from "@/lib/format";
import { useMe } from "@/lib/me";

const SEVERITY = { high: "High", medium: "Medium", low: "Low" };

function PositionEditor({ p, onChange, onRemove }: { p: Position; onChange: (p: Position) => void; onRemove: () => void }) {
  const set = (k: keyof Position) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) =>
    onChange({ ...p, [k]: e.target.value });
  return (
    <div className="card card-pad stack" style={{ gap: 10 }}>
      <div className="row">
        <input className="grow" value={p.title} onChange={set("title")} style={{ fontWeight: 600 }} aria-label="Title" />
        <select value={p.severity} onChange={set("severity")} style={{ width: 140 }} aria-label="Default risk">
          <option value="high">High risk</option><option value="medium">Medium risk</option><option value="low">Low risk</option>
        </select>
        <button className="btn-quiet btn-small" onClick={onRemove}>Remove</button>
      </div>
      <label>What we want<textarea rows={3} value={p.standard} onChange={set("standard")} /></label>
      <label>What we can accept<textarea rows={2} value={p.fallback} onChange={set("fallback")} /></label>
      <label>Always raise<textarea rows={2} value={p.red_flags} onChange={set("red_flags")} /></label>
    </div>
  );
}

export default function PlaybookPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const me = useMe();
  const [pb, setPb] = useState<Playbook | null>(null);
  const [draft, setDraft] = useState<Position[] | null>(null);
  const [lawyer, setLawyer] = useState(me.user.name);
  const [confirmed, setConfirmed] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(() => api.get<Playbook>(`/playbooks/${id}`).then(setPb), [id]);
  useEffect(() => { load(); }, [load]);
  if (!pb) return <div className="empty">Loading…</div>;

  const canEdit = atLeast(me.user.role, "partner");

  async function save() {
    setError("");
    try {
      await api.put(`/playbooks/${id}`, { name: pb!.name, description: pb!.description, positions: draft });
      setDraft(null);
      load();
    } catch (e) { setError((e as Error).message); }
  }

  async function approve() {
    setError("");
    try {
      await api.post(`/playbooks/${id}/validate`, { lawyer_name: lawyer });
      setConfirmed(false);
      load();
    } catch (e) { setError((e as Error).message); }
  }

  function newPosition(): Position {
    return { id: `custom_${Date.now()}`, title: "New point", standard: "", fallback: "", red_flags: "", severity: "medium" };
  }

  return (
    <>
      <div className="page-head">
        <div>
          <div className="faint"><Link href="/playbooks">Review playbooks</Link></div>
          <h1>{pb.name}</h1>
          <p>{pb.description}</p>
        </div>
        {canEdit && !draft && <button onClick={() => setDraft(pb.positions ?? [])}>Edit</button>}
      </div>

      {pb.validated_by ? (
        <div className="notice notice-ok" style={{ marginBottom: 20 }}><p>Approved by {pb.validated_by} {when(pb.validated_at)}. Any edit will ask for approval again.</p></div>
      ) : (
        <div className="notice notice-warn" style={{ marginBottom: 20 }}>
          <p>{pb.is_starter ? "Starter playbook from Nexus. " : ""}No lawyer at your firm has approved this playbook yet. Reviews that use it are marked accordingly.</p>
        </div>
      )}
      {error && <div className="notice notice-bad" style={{ marginBottom: 20 }}><p>{error}</p></div>}

      {draft ? (
        <div className="stack">
          {draft.map((p, i) => (
            <PositionEditor key={p.id} p={p}
              onChange={(np) => setDraft(draft.map((x, j) => (j === i ? np : x)))}
              onRemove={() => setDraft(draft.filter((_, j) => j !== i))} />
          ))}
          <div className="row">
            <button onClick={() => setDraft([...draft, newPosition()])}>Add a point</button>
            <span className="grow" />
            <button className="btn-quiet" onClick={() => setDraft(null)}>Cancel</button>
            <button className="btn-primary" onClick={save}>Save changes</button>
          </div>
        </div>
      ) : (
        <div className="stack">
          {(pb.positions ?? []).map((p, i) => (
            <div key={p.id} className="card card-pad stack" style={{ gap: 8 }}>
              <div className="row" style={{ justifyContent: "space-between" }}>
                <h3>{i + 1}. {p.title}</h3>
                <span className={`pill ${p.severity === "high" ? "pill-bad" : ""}`}>{SEVERITY[p.severity]} risk</span>
              </div>
              <p><strong>What we want.</strong> {p.standard}</p>
              <p className="muted"><strong>What we can accept.</strong> {p.fallback}</p>
              <p className="muted"><strong>Always raise.</strong> {p.red_flags}</p>
            </div>
          ))}

          {canEdit && !pb.validated_by && (
            <div className="card card-pad stack">
              <h3>Approve this playbook</h3>
              <label>Approving lawyer<input value={lawyer} onChange={(e) => setLawyer(e.target.value)} /></label>
              <label style={{ flexDirection: "row", alignItems: "flex-start", fontWeight: 400 }}>
                <input type="checkbox" style={{ width: "auto", marginTop: 4 }} checked={confirmed} onChange={(e) => setConfirmed(e.target.checked)} />
                <span>I am a qualified lawyer at this firm. I have read every point above and confirm it reflects the firm&apos;s position for the jurisdictions we practise in.</span>
              </label>
              <div className="row"><button className="btn-ok" disabled={!confirmed || lawyer.trim().length < 2} onClick={approve}>Approve playbook</button></div>
            </div>
          )}
        </div>
      )}
    </>
  );
}

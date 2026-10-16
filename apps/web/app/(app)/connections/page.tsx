"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { api, can, type Connection, type ConnectorSpec } from "@/lib/api";
import { when } from "@/lib/format";
import { useMe } from "@/lib/me";

const COLLECT: Record<Connection["collect_status"], { label: string; tone: string }> = {
  never: { label: "Not read yet", tone: "pill" },
  queued: { label: "Waiting to read", tone: "pill pill-brand" },
  running: { label: "Reading", tone: "pill pill-brand" },
  done: { label: "Read", tone: "pill pill-ok" },
  failed: { label: "Could not read", tone: "pill pill-bad" },
};

export default function Connections() {
  const me = useMe();
  const manage = can(me, "manage_connections");
  const [specs, setSpecs] = useState<ConnectorSpec[]>([]);
  const [conns, setConns] = useState<Connection[] | null>(null);
  const [kind, setKind] = useState("snowflake");
  const [label, setLabel] = useState("");
  const [values, setValues] = useState<Record<string, string>>({});
  const [error, setError] = useState("");
  const [tests, setTests] = useState<Record<string, { ok: boolean; message: string }>>({});
  const [busy, setBusy] = useState<string | null>(null);
  const dialog = useRef<HTMLDialogElement>(null);

  const load = () => api.get<Connection[]>("/connections").then(setConns);
  useEffect(() => {
    api.get<ConnectorSpec[]>("/connections/kinds").then(setSpecs);
    load();
  }, []);
  // Refresh while Nexus is reading a connection.
  useEffect(() => {
    if (!conns?.some((c) => c.collect_status === "queued" || c.collect_status === "running")) return;
    const t = setTimeout(load, 2000);
    return () => clearTimeout(t);
  }, [conns]);

  const spec = specs.find((s) => s.kind === kind);

  function open() {
    setError(""); setLabel(""); setValues({}); setKind(specs[0]?.kind ?? "snowflake");
    dialog.current?.showModal();
  }

  async function add(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    try {
      const defaults = Object.fromEntries((spec?.fields ?? []).filter((f) => f.default).map((f) => [f.name, f.default]));
      await api.post("/connections", { kind, label, values: { ...defaults, ...values } });
      dialog.current?.close();
      load();
    } catch (err) { setError((err as Error).message); }
  }

  async function test(c: Connection) {
    setBusy(c.id);
    try { setTests({ ...tests, [c.id]: await api.post(`/connections/${c.id}/test`) }); load(); }
    finally { setBusy(null); }
  }

  async function collect(c: Connection) {
    try { await api.post(`/connections/${c.id}/collect`); load(); }
    catch (err) { setTests({ ...tests, [c.id]: { ok: false, message: (err as Error).message } }); }
  }

  async function remove(c: Connection) {
    if (!confirm(`Remove ${c.label}?`)) return;
    try { await api.del(`/connections/${c.id}`); load(); }
    catch (err) { setTests({ ...tests, [c.id]: { ok: false, message: (err as Error).message } }); }
  }

  return (
    <div className="stack" style={{ gap: 24 }}>
      <div className="page-head" style={{ marginBottom: 0 }}>
        <div>
          <h1>Connections</h1>
          <p>Nexus reads tables and columns from these warehouses, only ever with read-only queries.</p>
        </div>
        {manage && <button className="btn-primary" onClick={open}>Add a connection</button>}
      </div>

      {conns === null ? <div className="empty">Loading…</div> : conns.length === 0 ? (
        <div className="card card-pad stack">
          <p className="muted">No connections yet.</p>
          <p className="faint">To try Nexus without a warehouse, run <code>cd services/api && uv run nexus-seed-demo --email {me.user.email}</code>. It creates two demo warehouses and connects them here.</p>
        </div>
      ) : conns.map((c) => {
        const status = COLLECT[c.collect_status];
        const result = tests[c.id];
        return (
          <div key={c.id} className="card card-pad stack">
            <div className="row" style={{ justifyContent: "space-between", alignItems: "flex-start" }}>
              <div>
                <div style={{ fontWeight: 600 }}>{c.label}</div>
                <div className="faint">
                  {specs.find((s) => s.kind === c.kind)?.name ?? c.kind}
                  {c.config.database ? ` · ${c.config.database}` : ""}{c.config.host ? ` · ${c.config.host}` : ""}
                  {!c.verified && " · not yet tested against a real account"}
                </div>
              </div>
              <span className={status.tone}>{status.label}</span>
            </div>
            {c.collect_msg && <p className="muted">{c.collect_msg}{c.collected_at ? ` (${when(c.collected_at)})` : ""}</p>}
            {(result || c.last_test_msg) && (
              <div className={`notice ${(result ? result.ok : c.last_test_ok) ? "notice-ok" : "notice-bad"}`}>
                <p>{result ? result.message : c.last_test_msg}</p>
              </div>
            )}
            {manage && (
              <div className="row" style={{ justifyContent: "flex-end" }}>
                <button className="btn-quiet" onClick={() => remove(c)}>Remove</button>
                <button className="btn-quiet" disabled={busy === c.id} onClick={() => test(c)}>{busy === c.id ? "Testing…" : "Test connection"}</button>
                <button className="btn-primary" disabled={c.collect_status === "queued" || c.collect_status === "running"}
                  onClick={() => collect(c)}>Read tables and columns</button>
              </div>
            )}
          </div>
        );
      })}

      {conns && conns.some((c) => c.collect_status === "done") && (
        <p className="muted">Everything Nexus reads arrives as a proposal. <Link href="/knowledge">Review it in the knowledge graph.</Link></p>
      )}

      <dialog ref={dialog}>
        <form className="card-pad stack" onSubmit={add}>
          <h2>Add a connection</h2>
          <label>Kind
            <select value={kind} onChange={(e) => { setKind(e.target.value); setValues({}); }}>
              {specs.map((s) => <option key={s.kind} value={s.kind}>{s.name}</option>)}
            </select>
            {spec && <span className="hint">{spec.description}</span>}
          </label>
          <label>Name<input required value={label} onChange={(e) => setLabel(e.target.value)} placeholder="e.g. Sales warehouse" /></label>
          {spec?.fields.map((f) => (
            <label key={f.name}>{f.label}{!f.required && <span className="hint"> Optional.</span>}
              {f.options.length ? (
                <select value={values[f.name] ?? f.default} onChange={(e) => setValues({ ...values, [f.name]: e.target.value })}>
                  {f.options.map((o) => <option key={o} value={o}>{o}</option>)}
                </select>
              ) : f.multiline ? (
                <textarea rows={4} value={values[f.name] ?? ""} onChange={(e) => setValues({ ...values, [f.name]: e.target.value })} />
              ) : (
                <input type={f.secret ? "password" : "text"} required={f.required} placeholder={f.placeholder || f.default}
                  autoComplete="off" value={values[f.name] ?? ""} onChange={(e) => setValues({ ...values, [f.name]: e.target.value })} />
              )}
              {f.help && <span className="hint">{f.help}</span>}
            </label>
          ))}
          {error && <div className="notice notice-bad"><p>{error}</p></div>}
          <div className="row" style={{ justifyContent: "flex-end" }}>
            <button type="button" className="btn-quiet" onClick={() => dialog.current?.close()}>Cancel</button>
            <button className="btn-primary">Add</button>
          </div>
        </form>
      </dialog>
    </div>
  );
}

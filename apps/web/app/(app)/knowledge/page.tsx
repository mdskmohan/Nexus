"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { api, can, type GraphSummary, type ItemKind, type JoinPath, type KgItem } from "@/lib/api";
import { when } from "@/lib/format";
import { useMe } from "@/lib/me";

type Tab = "review" | "tables" | "joins" | "metrics" | "paths" | "versions";
const TABS: { id: Tab; label: string }[] = [
  { id: "review", label: "Waiting for review" },
  { id: "tables", label: "Tables" },
  { id: "joins", label: "Joins" },
  { id: "metrics", label: "Metrics and entities" },
  { id: "paths", label: "Join paths" },
  { id: "versions", label: "Versions" },
];

const STATUS_TONE: Record<string, string> = {
  proposed: "pill pill-warn", approved: "pill pill-ok", rejected: "pill pill-bad", deprecated: "pill",
};
const KIND_LABEL: Record<ItemKind, string> = {
  table: "Tables", column: "Columns", join: "Joins", metric: "Metrics", entity: "Entities",
};

function Status({ item }: { item: KgItem }) {
  return (
    <span className={STATUS_TONE[item.status]}>
      {item.status === "deprecated" ? "retired" : item.status}
      {item.missing_since ? " · no longer in warehouse" : ""}
    </span>
  );
}

function Evidence({ item }: { item: KgItem }) {
  const e = item.attrs.evidence ?? {};
  const parts = [
    e.declared && "declared foreign key",
    e.name_match && `names match (${e.name_match})`,
    e.overlap !== undefined && `${Math.round(e.overlap * 100)}% of ${e.sampled} sampled values found`,
    e.right_key_ratio !== undefined && (e.right_key_ratio >= 0.98 ? "target is a key" : "target is not unique"),
    e.data_check_error && `data check failed: ${e.data_check_error}`,
  ].filter(Boolean);
  return (
    <div className="faint">
      {item.attrs.cross_source && <span className="pill pill-brand" style={{ marginRight: 6 }}>across warehouses</span>}
      Confidence {Math.round((item.attrs.confidence ?? 0) * 100)}% · {parts.join(" · ")}
    </div>
  );
}

export default function Knowledge() {
  const me = useMe();
  const steward = can(me, "approve_graph");
  const propose = can(me, "approve_graph") || can(me, "build_agents");
  const [tab, setTab] = useState<Tab>("review");
  const [summary, setSummary] = useState<GraphSummary | null>(null);
  const [items, setItems] = useState<KgItem[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [note, setNote] = useState("");
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null);
  const [open, setOpen] = useState<KgItem | null>(null);

  const load = async () => {
    setSummary(await api.get<GraphSummary>("/graph/summary"));
    setItems(await api.get<KgItem[]>("/graph/items"));
  };
  useEffect(() => { load(); }, []);

  const byKind = useMemo(() => {
    const out: Record<string, KgItem[]> = {};
    for (const i of items) (out[i.kind] ??= []).push(i);
    return out;
  }, [items]);
  const proposed = items.filter((i) => i.status === "proposed" && i.kind !== "column");
  const tables = (byKind.table ?? []).filter((t) => t.status !== "rejected");
  const approvedTables = tables.filter((t) => t.status === "approved");

  function toggle(id: string) {
    const next = new Set(selected);
    next.has(id) ? next.delete(id) : next.add(id);
    setSelected(next);
  }

  async function decide(decision: "approve" | "reject", ids: string[]) {
    setMessage(null);
    try {
      const r = await api.post<{ version: number | null; approved: number; deprecated: number; rejected: number }>(
        "/graph/review", { item_ids: ids, decision, note });
      const parts = [r.approved && `${r.approved} approved`, r.deprecated && `${r.deprecated} retired`, r.rejected && `${r.rejected} rejected`].filter(Boolean);
      setMessage({ ok: true, text: `${parts.join(", ") || "Nothing changed"}.${r.version ? ` The graph is now at version ${r.version}.` : ""}` });
      setSelected(new Set()); setNote(""); setOpen(null);
      load();
    } catch (err) { setMessage({ ok: false, text: (err as Error).message }); }
  }

  async function show(item: KgItem) {
    setOpen(await api.get<KgItem>(`/graph/items/${item.id}`));
  }

  return (
    <div className="stack" style={{ gap: 20 }}>
      <div className="page-head" style={{ marginBottom: 0 }}>
        <div>
          <h1>Knowledge graph</h1>
          <p>What is true about your data. Agents use only what a steward has approved.</p>
        </div>
        {summary && <span className="pill pill-brand">Version {summary.version}</span>}
      </div>

      {summary && items.length === 0 && (
        <div className="card card-pad"><p className="muted">Nothing here yet. <Link href="/connections">Connect a warehouse</Link> and read its tables.</p></div>
      )}
      {message && <div className={`notice ${message.ok ? "notice-ok" : "notice-bad"}`}><p>{message.text}</p></div>}

      <div className="tabs">
        {TABS.map((t) => (
          <button key={t.id} className={`tab ${tab === t.id ? "active" : ""}`} onClick={() => setTab(t.id)}>
            {t.label}{t.id === "review" && proposed.length ? ` (${proposed.length})` : ""}
          </button>
        ))}
      </div>

      {tab === "review" && (
        <div className="stack">
          {proposed.length === 0 ? <p className="muted">Nothing is waiting for review.</p> : (
            <>
              <p className="muted">
                Approving a table also approves its columns. A join, metric or entity can be approved once its tables are.
                {!steward && " Only a steward can approve."}
              </p>
              {(["table", "join", "metric", "entity"] as ItemKind[]).map((kind) => {
                const group = proposed.filter((i) => i.kind === kind);
                if (!group.length) return null;
                const allOn = group.every((i) => selected.has(i.id));
                return (
                  <section key={kind} className="card">
                    <div className="card-pad row" style={{ justifyContent: "space-between" }}>
                      <h2 style={{ margin: 0 }}>{KIND_LABEL[kind]} ({group.length})</h2>
                      {steward && (
                        <button className="btn-quiet btn-small" onClick={() => {
                          const next = new Set(selected);
                          group.forEach((i) => (allOn ? next.delete(i.id) : next.add(i.id)));
                          setSelected(next);
                        }}>{allOn ? "Clear" : "Select all"}</button>
                      )}
                    </div>
                    <table>
                      <tbody>
                        {group.map((i) => (
                          <tr key={i.id}>
                            {steward && <td style={{ width: 32 }}><input type="checkbox" checked={selected.has(i.id)} onChange={() => toggle(i.id)} /></td>}
                            <td>
                              <div style={{ fontWeight: 600 }}>{i.name}</div>
                              {i.kind === "join" ? <Evidence item={i} /> : (
                                <div className="faint">
                                  {i.connection_label}{i.kind === "table" ? ` · ${i.attrs.column_count} columns · ${i.attrs.table_kind}` : ""}
                                  {i.kind === "metric" ? ` · ${i.attrs.measure}${i.attrs.filter ? ` where ${i.attrs.filter}` : ""} on ${i.attrs.table}` : ""}
                                  {i.kind === "entity" ? ` · ${(i.attrs.tables ?? []).join(", ")}` : ""}
                                  {i.proposed_by_name ? ` · proposed by ${i.proposed_by_name}` : ""}
                                  {i.attrs.comment ? ` · “${i.attrs.comment}”` : ""}
                                </div>
                              )}
                            </td>
                            <td style={{ textAlign: "right" }}>
                              {i.kind === "table" && <button className="btn-quiet btn-small" onClick={() => show(i)}>Columns</button>}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </section>
                );
              })}
              {steward && (
                <div className="card card-pad stack" style={{ position: "sticky", bottom: 12 }}>
                  <label>Note for the record (optional)<input value={note} onChange={(e) => setNote(e.target.value)} /></label>
                  <div className="row" style={{ justifyContent: "flex-end" }}>
                    <span className="faint">{selected.size} selected</span>
                    <button className="btn-quiet" disabled={!selected.size} onClick={() => decide("reject", [...selected])}>Reject</button>
                    <button className="btn-primary" disabled={!selected.size} onClick={() => decide("approve", [...selected])}>Approve</button>
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      )}

      {tab === "tables" && (
        <div className="card">
          <table>
            <thead><tr><th>Table</th><th>Connection</th><th>Status</th><th></th></tr></thead>
            <tbody>
              {tables.map((t) => (
                <tr key={t.id}>
                  <td><div style={{ fontWeight: 600 }}>{t.name}</div><div className="faint">{t.attrs.column_count} columns{t.description ? ` · ${t.description}` : ""}</div></td>
                  <td className="muted">{t.connection_label}</td>
                  <td><Status item={t} /></td>
                  <td style={{ textAlign: "right" }}>
                    <button className="btn-quiet btn-small" onClick={() => show(t)}>Details</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {tab === "joins" && (
        <div className="card">
          <table>
            <tbody>
              {(byKind.join ?? []).map((j) => (
                <tr key={j.id}>
                  <td><div style={{ fontWeight: 600 }}>{j.name}</div><Evidence item={j} /></td>
                  <td><Status item={j} /></td>
                  <td style={{ textAlign: "right" }}>
                    {steward && j.status === "approved" && <button className="btn-quiet btn-small" onClick={() => decide("reject", [j.id])}>Retire</button>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {tab === "metrics" && <MetricsTab items={items} tables={tables} propose={propose} steward={steward} onChange={load} onRetire={(id) => decide("reject", [id])} />}
      {tab === "paths" && <PathsTab tables={approvedTables} />}
      {tab === "versions" && <VersionsTab />}

      {open && (
        <div className="card card-pad stack">
          <div className="row" style={{ justifyContent: "space-between" }}>
            <div><h2 style={{ margin: 0 }}>{open.name}</h2><div className="faint">{open.connection_label} · {open.attrs.database}</div></div>
            <div className="row">
              <Status item={open} />
              {steward && open.status === "approved" && <button className="btn-quiet btn-small" onClick={() => decide("reject", [open.id])}>Retire</button>}
              <button className="btn-quiet btn-small" onClick={() => setOpen(null)}>Close</button>
            </div>
          </div>
          <table>
            <thead><tr><th>Column</th><th>Type</th><th>Notes</th><th>Status</th></tr></thead>
            <tbody>
              {open.columns?.map((c) => (
                <tr key={c.id}>
                  <td style={{ fontWeight: 600 }}>{c.attrs.column}</td>
                  <td className="muted">{c.attrs.raw_type}{c.attrs.nullable ? "" : " · required"}</td>
                  <td className="faint">{c.attrs.comment}{c.attrs.references ? " · declared key" : ""}</td>
                  <td><Status item={c} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function MetricsTab({ items, tables, propose, steward, onChange, onRetire }: {
  items: KgItem[]; tables: KgItem[]; propose: boolean; steward: boolean; onChange: () => void; onRetire: (id: string) => void;
}) {
  const [metric, setMetric] = useState({ name: "", description: "", table_id: "", measure: "", filter: "" });
  const [entity, setEntity] = useState({ name: "", description: "", table_ids: [] as string[] });
  const [error, setError] = useState("");
  const defined = items.filter((i) => (i.kind === "metric" || i.kind === "entity") && i.status !== "rejected");

  async function addMetric(e: React.FormEvent) {
    e.preventDefault(); setError("");
    try {
      await api.post("/graph/metrics", { ...metric, filter: metric.filter || null });
      setMetric({ name: "", description: "", table_id: "", measure: "", filter: "" }); onChange();
    } catch (err) { setError((err as Error).message); }
  }
  async function addEntity(e: React.FormEvent) {
    e.preventDefault(); setError("");
    try {
      await api.post("/graph/entities", entity);
      setEntity({ name: "", description: "", table_ids: [] }); onChange();
    } catch (err) { setError((err as Error).message); }
  }

  return (
    <div className="stack">
      <div className="card">
        <table>
          <tbody>
            {defined.length === 0 && <tr><td className="muted">No metrics or entities yet.</td></tr>}
            {defined.map((d) => (
              <tr key={d.id}>
                <td>
                  <div style={{ fontWeight: 600 }}>{d.name} <span className="faint">{d.kind}</span></div>
                  <div className="faint">
                    {d.kind === "metric" ? `${d.attrs.measure}${d.attrs.filter ? ` where ${d.attrs.filter}` : ""} on ${d.attrs.table}` : (d.attrs.tables ?? []).join(", ")}
                    {d.description ? ` · ${d.description}` : ""}
                  </div>
                </td>
                <td><Status item={d} /></td>
                <td style={{ textAlign: "right" }}>{steward && d.status === "approved" && <button className="btn-quiet btn-small" onClick={() => onRetire(d.id)}>Retire</button>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {error && <div className="notice notice-bad"><p>{error}</p></div>}
      {propose && (
        <div className="grid-2">
          <form className="card card-pad stack" onSubmit={addMetric}>
            <h2>Propose a metric</h2>
            <label>Name<input required value={metric.name} onChange={(e) => setMetric({ ...metric, name: e.target.value })} placeholder="Net revenue" /></label>
            <label>Table
              <select required value={metric.table_id} onChange={(e) => setMetric({ ...metric, table_id: e.target.value })}>
                <option value="">Choose a table</option>
                {tables.map((t) => <option key={t.id} value={t.id}>{t.name} ({t.connection_label})</option>)}
              </select>
            </label>
            <label>Measure<input required value={metric.measure} onChange={(e) => setMetric({ ...metric, measure: e.target.value })} placeholder="sum(net_amount)" />
              <span className="hint">An aggregate over the table&apos;s columns, in that warehouse&apos;s SQL.</span></label>
            <label>Filter (optional)<input value={metric.filter} onChange={(e) => setMetric({ ...metric, filter: e.target.value })} placeholder="status = 'complete'" /></label>
            <label>Description<input value={metric.description} onChange={(e) => setMetric({ ...metric, description: e.target.value })} /></label>
            <button className="btn-primary">Propose metric</button>
          </form>
          <form className="card card-pad stack" onSubmit={addEntity}>
            <h2>Propose an entity</h2>
            <label>Name<input required value={entity.name} onChange={(e) => setEntity({ ...entity, name: e.target.value })} placeholder="Customer" /></label>
            <label>Tables that represent it
              <select multiple size={6} value={entity.table_ids}
                onChange={(e) => setEntity({ ...entity, table_ids: Array.from(e.target.selectedOptions).map((o) => o.value) })}>
                {tables.map((t) => <option key={t.id} value={t.id}>{t.name} ({t.connection_label})</option>)}
              </select>
            </label>
            <label>Description<input value={entity.description} onChange={(e) => setEntity({ ...entity, description: e.target.value })} /></label>
            <button className="btn-primary">Propose entity</button>
          </form>
        </div>
      )}
    </div>
  );
}

function PathsTab({ tables }: { tables: KgItem[] }) {
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [paths, setPaths] = useState<JoinPath[] | null>(null);

  async function find(e: React.FormEvent) {
    e.preventDefault();
    setPaths(await api.get<JoinPath[]>(`/graph/paths?from_table=${from}&to_table=${to}`));
  }
  return (
    <div className="stack">
      <p className="muted">How two approved tables can be joined, using only approved joins. Agents plan their queries the same way.</p>
      <form className="row card card-pad" onSubmit={find} style={{ alignItems: "flex-end" }}>
        <label style={{ flex: 1 }}>From
          <select required value={from} onChange={(e) => setFrom(e.target.value)}>
            <option value="">Choose a table</option>
            {tables.map((t) => <option key={t.id} value={t.id}>{t.name} ({t.connection_label})</option>)}
          </select>
        </label>
        <label style={{ flex: 1 }}>To
          <select required value={to} onChange={(e) => setTo(e.target.value)}>
            <option value="">Choose a table</option>
            {tables.map((t) => <option key={t.id} value={t.id}>{t.name} ({t.connection_label})</option>)}
          </select>
        </label>
        <button className="btn-primary">Find paths</button>
      </form>
      {paths && (paths.length === 0 ? <p className="muted">No approved path joins these tables.</p> : paths.map((p, n) => (
        <div key={n} className="card card-pad stack" style={{ gap: 4 }}>
          <div style={{ fontWeight: 600 }}>{p.hops} {p.hops === 1 ? "join" : "joins"}</div>
          {p.joins.map((j) => (
            <div key={j.id} className="muted">{j.name}{j.cross_source && <span className="pill pill-brand" style={{ marginLeft: 6 }}>across warehouses</span>}</div>
          ))}
        </div>
      )))}
    </div>
  );
}

function VersionsTab() {
  const [versions, setVersions] = useState<{ number: number; summary: Record<string, unknown>; created_at: string; created_by_name: string | null }[]>([]);
  useEffect(() => { api.get<typeof versions>("/graph/versions").then(setVersions); }, []);
  return (
    <div className="card">
      <table>
        <thead><tr><th>Version</th><th>Change</th><th>By</th><th>When</th></tr></thead>
        <tbody>
          {versions.length === 0 && <tr><td className="muted" colSpan={4}>Nothing has been approved yet.</td></tr>}
          {versions.map((v) => (
            <tr key={v.number}>
              <td style={{ fontWeight: 600 }}>{v.number}</td>
              <td className="muted">{[v.summary.approved ? `${v.summary.approved} approved` : "", v.summary.deprecated ? `${v.summary.deprecated} retired` : ""].filter(Boolean).join(", ")}{v.summary.note ? ` · ${v.summary.note}` : ""}</td>
              <td className="muted">{v.created_by_name}</td>
              <td className="muted">{when(v.created_at)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

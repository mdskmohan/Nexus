"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  ArrowRight, Box, Check, Database, GitBranch, GitMerge, History, Inbox, KeyRound, Link2, Network, Plus, Route,
  Sigma, Sparkles, Table2, X, type LucideIcon,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Callout } from "@/components/ui/callout";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { Dialog } from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { Field, Input, Select } from "@/components/ui/form";
import { PageHeader } from "@/components/ui/page-header";
import { StatCard } from "@/components/ui/stat-card";
import { StatusPill, type Tone } from "@/components/ui/status-pill";
import { Table, Td, Th, Tr } from "@/components/ui/table";
import { Tabs } from "@/components/ui/tabs";
import { api, can, type GraphSummary, type ItemKind, type JoinPath, type KgItem } from "@/lib/api";
import { when } from "@/lib/format";
import { useMe } from "@/lib/me";
import { cn } from "@/lib/utils";

type Tab = "review" | "tables" | "joins" | "metrics" | "paths" | "versions";

const STATUS: Record<string, { tone: Tone; label: string }> = {
  proposed: { tone: "warning", label: "Proposed" },
  approved: { tone: "success", label: "Approved" },
  rejected: { tone: "danger", label: "Rejected" },
  deprecated: { tone: "neutral", label: "Retired" },
};
const KIND: Record<ItemKind, { label: string; icon: LucideIcon; tile: string }> = {
  table: { label: "Tables", icon: Table2, tile: "bg-primary-soft text-primary" },
  column: { label: "Columns", icon: Box, tile: "bg-muted text-muted-foreground" },
  join: { label: "Joins", icon: GitMerge, tile: "bg-info-soft text-info-soft-foreground" },
  metric: { label: "Metrics", icon: Sigma, tile: "bg-success-soft text-success-soft-foreground" },
  entity: { label: "Entities", icon: Sparkles, tile: "bg-warning-soft text-warning-soft-foreground" },
};

function Status({ item }: { item: KgItem }) {
  const s = STATUS[item.status];
  return (
    <span className="inline-flex items-center gap-1.5">
      <StatusPill tone={s.tone} dot>{s.label}</StatusPill>
      {item.missing_since && <StatusPill tone="danger">Gone from warehouse</StatusPill>}
    </span>
  );
}

function KindIcon({ kind }: { kind: ItemKind }) {
  const k = KIND[kind];
  return <span className={cn("rounded-md p-1.5", k.tile)}><k.icon className="size-4" /></span>;
}

function Confidence({ value }: { value: number }) {
  const pct = Math.round(value * 100);
  return (
    <span className="inline-flex items-center gap-2">
      <span className="h-1.5 w-16 overflow-hidden rounded-full bg-muted">
        <span className={cn("block h-full rounded-full", pct >= 80 ? "bg-success" : pct >= 60 ? "bg-warning" : "bg-danger")} style={{ width: `${pct}%` }} />
      </span>
      <span className="num text-caption text-muted-foreground">{pct}%</span>
    </span>
  );
}

function Evidence({ item }: { item: KgItem }) {
  const e = item.attrs.evidence ?? {};
  const chips: { text: string; icon: LucideIcon }[] = [
    e.declared && { text: "Declared foreign key", icon: KeyRound },
    e.name_match && { text: `Names match: ${e.name_match}`, icon: Link2 },
    e.overlap !== undefined && { text: `${Math.round(e.overlap * 100)}% of ${e.sampled} sampled values found`, icon: Database },
    e.right_key_ratio !== undefined && { text: e.right_key_ratio >= 0.98 ? "Target is a key" : "Target is not unique", icon: KeyRound },
  ].filter(Boolean) as { text: string; icon: LucideIcon }[];
  return (
    <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
      {item.attrs.cross_source && <StatusPill tone="primary" icon={<Network />}>Across warehouses</StatusPill>}
      {chips.map((c) => <StatusPill key={c.text} tone="neutral" icon={<c.icon />}>{c.text}</StatusPill>)}
      {e.data_check_error && <StatusPill tone="danger">Data check failed</StatusPill>}
    </div>
  );
}

function describe(i: KgItem): string {
  if (i.kind === "table") return `${i.connection_label} · ${i.attrs.column_count} columns · ${i.attrs.table_kind}`;
  if (i.kind === "metric") return `${i.attrs.measure}${i.attrs.filter ? ` where ${i.attrs.filter}` : ""} on ${i.attrs.table}`;
  if (i.kind === "entity") return (i.attrs.tables ?? []).join(", ");
  return i.connection_label ?? "";
}

export default function Knowledge() {
  const me = useMe();
  const steward = can(me, "approve_graph");
  const propose = can(me, "approve_graph") || can(me, "build_agents");
  const [tab, setTab] = useState<Tab>("review");
  const [summary, setSummary] = useState<GraphSummary | null>(null);
  const [items, setItems] = useState<KgItem[] | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [note, setNote] = useState("");
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null);
  const [open, setOpen] = useState<KgItem | null>(null);
  const detail = useRef<HTMLDialogElement>(null);

  const load = async () => {
    setSummary(await api.get<GraphSummary>("/graph/summary"));
    setItems(await api.get<KgItem[]>("/graph/items"));
  };
  useEffect(() => { load(); }, []);

  const all = items ?? [];
  const byKind = useMemo(() => {
    const out: Record<string, KgItem[]> = {};
    for (const i of all) (out[i.kind] ??= []).push(i);
    return out;
  }, [all]);
  const proposed = all.filter((i) => i.status === "proposed" && i.kind !== "column");
  const tables = (byKind.table ?? []).filter((t) => t.status !== "rejected");
  const approvedTables = tables.filter((t) => t.status === "approved");

  function toggle(id: string) {
    const next = new Set(selected);
    if (next.has(id)) next.delete(id); else next.add(id);
    setSelected(next);
  }

  async function decide(decision: "approve" | "reject", ids: string[]) {
    setMessage(null);
    try {
      const r = await api.post<{ version: number | null; approved: number; deprecated: number; rejected: number }>(
        "/graph/review", { item_ids: ids, decision, note });
      const parts = [r.approved && `${r.approved} approved`, r.deprecated && `${r.deprecated} retired`, r.rejected && `${r.rejected} rejected`].filter(Boolean);
      setMessage({ ok: true, text: `${parts.join(", ") || "Nothing changed"}.${r.version ? ` The graph is now at version ${r.version}.` : ""}` });
      setSelected(new Set()); setNote(""); detail.current?.close();
      load();
    } catch (err) { setMessage({ ok: false, text: (err as Error).message }); }
  }

  async function show(item: KgItem) {
    setOpen(await api.get<KgItem>(`/graph/items/${item.id}`));
    detail.current?.showModal();
  }

  const tabs = [
    { id: "review" as Tab, label: "Waiting for review", icon: <Inbox />, count: proposed.length },
    { id: "tables" as Tab, label: "Tables", icon: <Table2 /> },
    { id: "joins" as Tab, label: "Joins", icon: <GitMerge /> },
    { id: "metrics" as Tab, label: "Metrics and entities", icon: <Sigma /> },
    { id: "paths" as Tab, label: "Join paths", icon: <Route /> },
    { id: "versions" as Tab, label: "Versions", icon: <History /> },
  ];

  return (
    <>
      <PageHeader title="Knowledge graph" description="What is true about your data. Agents use only what a steward has approved."
        actions={summary && <StatusPill tone="primary" icon={<GitBranch />}>Version {summary.version}</StatusPill>} />

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Waiting for review" value={proposed.length} icon={Inbox} tone={proposed.length ? "warning" : "neutral"} sub="Tables, joins, metrics, entities" />
        <StatCard label="Approved tables" value={approvedTables.length} icon={Table2} tone="primary" sub={`of ${tables.length} read from warehouses`} />
        <StatCard label="Approved joins" value={(byKind.join ?? []).filter((j) => j.status === "approved").length} icon={GitMerge} tone="info"
          sub={`${(byKind.join ?? []).filter((j) => j.status === "approved" && j.attrs.cross_source).length} across warehouses`} />
        <StatCard label="Metrics" value={(byKind.metric ?? []).filter((m) => m.status === "approved").length} icon={Sigma} tone="success" sub="Approved definitions" />
      </div>

      {items && items.length === 0 && (
        <Card>
          <EmptyState icon={Network} title="The graph is empty"
            description="Connect a warehouse and read its tables. Everything Nexus finds arrives here as a proposal."
            action={<Link href="/connections"><Button><Plus />Connect a warehouse</Button></Link>} />
        </Card>
      )}
      {message && <Callout tone={message.ok ? "success" : "danger"}>{message.text}</Callout>}

      <Tabs tabs={tabs} value={tab} onChange={setTab} />

      {tab === "review" && (
        <div className="space-y-4">
          {proposed.length === 0 ? (
            <Card><EmptyState icon={Check} title="Nothing is waiting for review" description="New proposals appear here after Nexus reads a connection, or when someone proposes a metric or entity." /></Card>
          ) : (
            <>
              <p className="text-body text-muted-foreground">
                Approving a table also approves its columns. A join, metric or entity can be approved once its tables are.
                {!steward && " Only a steward can approve."}
              </p>
              {(["table", "join", "metric", "entity"] as ItemKind[]).map((kind) => {
                const group = proposed.filter((i) => i.kind === kind);
                if (!group.length) return null;
                const allOn = group.every((i) => selected.has(i.id));
                const K = KIND[kind];
                return (
                  <Card key={kind}>
                    <CardHeader icon={<K.icon />} title={`${K.label}`} description={`${group.length} waiting`}
                      actions={steward && (
                        <Button variant="ghost" size="sm" onClick={() => {
                          const next = new Set(selected);
                          group.forEach((i) => (allOn ? next.delete(i.id) : next.add(i.id)));
                          setSelected(next);
                        }}>{allOn ? "Clear" : "Select all"}</Button>
                      )} />
                    <ul className="divide-y divide-border">
                      {group.map((i) => (
                        <li key={i.id} className={cn("flex items-start gap-3 px-5 py-3.5 transition-colors", selected.has(i.id) && "bg-primary-soft/50")}>
                          {steward && <input type="checkbox" className="mt-1" checked={selected.has(i.id)} onChange={() => toggle(i.id)} aria-label={`Select ${i.name}`} />}
                          <div className="min-w-0 flex-1">
                            <div className="flex flex-wrap items-center gap-2">
                              <span className="font-medium text-foreground">{i.name}</span>
                              {i.kind === "join" && <Confidence value={i.attrs.confidence ?? 0} />}
                            </div>
                            {i.kind === "join" ? <Evidence item={i} /> : (
                              <p className="text-caption text-muted-foreground">
                                {describe(i)}{i.proposed_by_name ? ` · proposed by ${i.proposed_by_name}` : ""}
                                {i.attrs.comment ? ` · “${i.attrs.comment}”` : ""}
                              </p>
                            )}
                          </div>
                          {i.kind === "table" && <Button variant="ghost" size="sm" onClick={() => show(i)}>Columns<ArrowRight /></Button>}
                        </li>
                      ))}
                    </ul>
                  </Card>
                );
              })}
              {steward && (
                <div className="sticky bottom-4 z-10 flex flex-wrap items-center gap-3 rounded-lg border border-border bg-card/95 p-3 shadow-lg backdrop-blur">
                  <Input className="min-w-[200px] flex-1" placeholder="Note for the record (optional)" value={note} onChange={(e) => setNote(e.target.value)} />
                  <span className="num text-caption text-muted-foreground">{selected.size} selected</span>
                  <Button variant="outline" disabled={!selected.size} onClick={() => decide("reject", [...selected])}><X />Reject</Button>
                  <Button disabled={!selected.size} onClick={() => decide("approve", [...selected])}><Check />Approve</Button>
                </div>
              )}
            </>
          )}
        </div>
      )}

      {tab === "tables" && (
        <Card>
          <Table>
            <thead><tr><Th>Table</Th><Th>Connection</Th><Th>Status</Th><Th /></tr></thead>
            <tbody>
              {tables.map((t) => (
                <Tr key={t.id}>
                  <Td>
                    <div className="flex items-center gap-3">
                      <KindIcon kind="table" />
                      <div>
                        <div className="font-medium text-foreground">{t.name}</div>
                        <div className="text-caption text-muted-foreground">{t.attrs.column_count} columns{t.description ? ` · ${t.description}` : ""}</div>
                      </div>
                    </div>
                  </Td>
                  <Td className="text-muted-foreground">{t.connection_label}</Td>
                  <Td><Status item={t} /></Td>
                  <Td className="text-right"><Button variant="ghost" size="sm" onClick={() => show(t)}>Details<ArrowRight /></Button></Td>
                </Tr>
              ))}
            </tbody>
          </Table>
        </Card>
      )}

      {tab === "joins" && (
        <Card>
          <ul className="divide-y divide-border">
            {(byKind.join ?? []).length === 0 && <li className="px-5 py-6 text-muted-foreground">No joins suggested yet.</li>}
            {(byKind.join ?? []).map((j) => (
              <li key={j.id} className="flex items-start gap-3 px-5 py-3.5">
                <KindIcon kind="join" />
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-medium text-foreground">{j.name}</span>
                    <Confidence value={j.attrs.confidence ?? 0} />
                  </div>
                  <Evidence item={j} />
                </div>
                <div className="flex items-center gap-2">
                  <Status item={j} />
                  {steward && j.status === "approved" && <Button variant="ghost" size="sm" onClick={() => decide("reject", [j.id])}>Retire</Button>}
                </div>
              </li>
            ))}
          </ul>
        </Card>
      )}

      {tab === "metrics" && <MetricsTab items={all} tables={tables} propose={propose} steward={steward} onChange={load} onRetire={(id) => decide("reject", [id])} />}
      {tab === "paths" && <PathsTab tables={approvedTables} />}
      {tab === "versions" && <VersionsTab />}

      <Dialog ref={detail} wide title={open?.name ?? ""} description={open ? `${open.connection_label} · ${open.attrs.database}` : undefined}>
        {open && (
          <div className="space-y-4">
            <div className="flex flex-wrap items-center gap-2">
              <Status item={open} />
              {open.attrs.comment && <span className="text-body text-muted-foreground">“{open.attrs.comment}”</span>}
              {steward && open.status === "approved" && <Button variant="outline" size="sm" className="ml-auto" onClick={() => decide("reject", [open.id])}>Retire table</Button>}
              {steward && open.status === "proposed" && <Button size="sm" className="ml-auto" onClick={() => decide("approve", [open.id])}><Check />Approve table</Button>}
            </div>
            <div className="max-h-[50vh] overflow-y-auto rounded-md border border-border">
              <Table>
                <thead><tr><Th>Column</Th><Th>Type</Th><Th>Notes</Th></tr></thead>
                <tbody>
                  {open.columns?.map((c) => (
                    <Tr key={c.id}>
                      <Td className="font-mono text-caption font-medium text-foreground">{c.attrs.column}</Td>
                      <Td className="text-caption text-muted-foreground">{c.attrs.raw_type}{c.attrs.nullable ? "" : " · required"}</Td>
                      <Td className="text-caption text-muted-foreground">
                        {c.attrs.references && <StatusPill tone="info" icon={<KeyRound />} className="mr-1.5">Declared key</StatusPill>}
                        {c.attrs.comment}
                      </Td>
                    </Tr>
                  ))}
                </tbody>
              </Table>
            </div>
          </div>
        )}
      </Dialog>
    </>
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
    <div className="space-y-4">
      <Card>
        {defined.length === 0 ? (
          <EmptyState icon={Sigma} title="No metrics or entities yet" description="Define what revenue or a customer means once, and every agent uses the same definition." />
        ) : (
          <ul className="divide-y divide-border">
            {defined.map((d) => (
              <li key={d.id} className="flex items-start gap-3 px-5 py-3.5">
                <KindIcon kind={d.kind} />
                <div className="min-w-0 flex-1">
                  <p className="font-medium text-foreground">{d.name}</p>
                  <p className="text-caption text-muted-foreground">
                    {d.kind === "metric" ? <span className="font-mono">{d.attrs.measure}{d.attrs.filter ? ` where ${d.attrs.filter}` : ""}</span> : null}
                    {d.kind === "metric" ? ` on ${d.attrs.table}` : (d.attrs.tables ?? []).join(", ")}
                    {d.description ? ` · ${d.description}` : ""}
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <Status item={d} />
                  {steward && d.status === "approved" && <Button variant="ghost" size="sm" onClick={() => onRetire(d.id)}>Retire</Button>}
                </div>
              </li>
            ))}
          </ul>
        )}
      </Card>
      {error && <Callout tone="danger">{error}</Callout>}
      {propose && (
        <div className="grid gap-4 lg:grid-cols-2">
          <Card>
            <CardHeader icon={<Sigma />} title="Propose a metric" description="An aggregate over one table, in that warehouse's SQL." />
            <CardBody>
              <form className="space-y-4" onSubmit={addMetric}>
                <Field label="Name"><Input required value={metric.name} onChange={(e) => setMetric({ ...metric, name: e.target.value })} placeholder="Net revenue" /></Field>
                <Field label="Table">
                  <Select required value={metric.table_id} onChange={(e) => setMetric({ ...metric, table_id: e.target.value })}>
                    <option value="">Choose a table</option>
                    {tables.map((t) => <option key={t.id} value={t.id}>{t.name} ({t.connection_label})</option>)}
                  </Select>
                </Field>
                <Field label="Measure"><Input required className="font-mono" value={metric.measure} onChange={(e) => setMetric({ ...metric, measure: e.target.value })} placeholder="sum(net_amount)" /></Field>
                <Field label="Filter" optional><Input className="font-mono" value={metric.filter} onChange={(e) => setMetric({ ...metric, filter: e.target.value })} placeholder="status = 'complete'" /></Field>
                <Field label="Description" optional><Input value={metric.description} onChange={(e) => setMetric({ ...metric, description: e.target.value })} /></Field>
                <Button><Plus />Propose metric</Button>
              </form>
            </CardBody>
          </Card>
          <Card>
            <CardHeader icon={<Sparkles />} title="Propose an entity" description="A business concept and the tables that hold it." />
            <CardBody>
              <form className="space-y-4" onSubmit={addEntity}>
                <Field label="Name"><Input required value={entity.name} onChange={(e) => setEntity({ ...entity, name: e.target.value })} placeholder="Customer" /></Field>
                <Field label="Tables that represent it" hint="Hold ⌘ or Ctrl to choose several.">
                  <Select multiple size={6} value={entity.table_ids}
                    onChange={(e) => setEntity({ ...entity, table_ids: Array.from(e.target.selectedOptions).map((o) => o.value) })}>
                    {tables.map((t) => <option key={t.id} value={t.id}>{t.name} ({t.connection_label})</option>)}
                  </Select>
                </Field>
                <Field label="Description" optional><Input value={entity.description} onChange={(e) => setEntity({ ...entity, description: e.target.value })} /></Field>
                <Button><Plus />Propose entity</Button>
              </form>
            </CardBody>
          </Card>
        </div>
      )}
    </div>
  );
}

function PathsTab({ tables }: { tables: KgItem[] }) {
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [paths, setPaths] = useState<JoinPath[] | null>(null);
  const name = (id: string) => tables.find((t) => t.id === id)?.name ?? "";

  async function find(e: React.FormEvent) {
    e.preventDefault();
    setPaths(await api.get<JoinPath[]>(`/graph/paths?from_table=${from}&to_table=${to}`));
  }
  return (
    <div className="space-y-4">
      <Card>
        <CardHeader icon={<Route />} title="Find a join path" description="How two approved tables connect, using only approved joins. Agents plan their queries the same way." />
        <CardBody>
          <form className="flex flex-wrap items-end gap-3" onSubmit={find}>
            <Field label="From" className="min-w-[220px] flex-1">
              <Select required value={from} onChange={(e) => setFrom(e.target.value)}>
                <option value="">Choose a table</option>
                {tables.map((t) => <option key={t.id} value={t.id}>{t.name} ({t.connection_label})</option>)}
              </Select>
            </Field>
            <Field label="To" className="min-w-[220px] flex-1">
              <Select required value={to} onChange={(e) => setTo(e.target.value)}>
                <option value="">Choose a table</option>
                {tables.map((t) => <option key={t.id} value={t.id}>{t.name} ({t.connection_label})</option>)}
              </Select>
            </Field>
            <Button><Route />Find paths</Button>
          </form>
        </CardBody>
      </Card>
      {paths && (paths.length === 0 ? <Callout tone="warning">No approved path joins these tables.</Callout> : paths.map((p, n) => (
        <Card key={n}>
          <CardBody>
            <div className="mb-3 flex items-center gap-2">
              <StatusPill tone="primary">{p.hops} {p.hops === 1 ? "join" : "joins"}</StatusPill>
              <span className="text-caption text-muted-foreground">{name(from)} → {name(to)}</span>
            </div>
            <ol className="relative space-y-3 border-l-2 border-dashed border-border-strong pl-5">
              {p.joins.map((j) => (
                <li key={j.id} className="relative">
                  <span className="absolute -left-[27px] top-1 flex size-3 items-center justify-center rounded-full border-2 border-primary bg-card" />
                  <span className="font-mono text-caption text-foreground">{j.name}</span>
                  {j.cross_source && <StatusPill tone="primary" icon={<Network />} className="ml-2">Across warehouses</StatusPill>}
                </li>
              ))}
            </ol>
          </CardBody>
        </Card>
      )))}
    </div>
  );
}

function VersionsTab() {
  const [versions, setVersions] = useState<{ number: number; summary: Record<string, unknown>; created_at: string; created_by_name: string | null }[]>([]);
  useEffect(() => { api.get<typeof versions>("/graph/versions").then(setVersions); }, []);
  return (
    <Card>
      {versions.length === 0 ? <EmptyState icon={History} title="No versions yet" description="Each approval creates a new graph version. Runs record the version they planned against." /> : (
        <Table>
          <thead><tr><Th>Version</Th><Th>Change</Th><Th>By</Th><Th>When</Th></tr></thead>
          <tbody>
            {versions.map((v) => (
              <Tr key={v.number}>
                <Td><StatusPill tone="primary" icon={<GitBranch />}>v{v.number}</StatusPill></Td>
                <Td className="text-muted-foreground">
                  {[v.summary.approved ? `${v.summary.approved} approved` : "", v.summary.deprecated ? `${v.summary.deprecated} retired` : ""].filter(Boolean).join(", ")}
                  {v.summary.note ? ` · ${v.summary.note}` : ""}
                </Td>
                <Td className="text-muted-foreground">{v.created_by_name}</Td>
                <Td className="text-muted-foreground">{when(v.created_at)}</Td>
              </Tr>
            ))}
          </tbody>
        </Table>
      )}
    </Card>
  );
}

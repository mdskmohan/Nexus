"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import {
  ArrowRight, BarChart3, Boxes, Building2, Cable, Database, Layers, Loader2, Plus, RefreshCw, Server, Snowflake, Trash2,
  Warehouse, Zap,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Callout } from "@/components/ui/callout";
import { Card } from "@/components/ui/card";
import { Dialog } from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { Field, Input, Select, Textarea } from "@/components/ui/form";
import { PageHeader } from "@/components/ui/page-header";
import { StatusPill, type Tone } from "@/components/ui/status-pill";
import { api, can, type Connection, type ConnectorSpec } from "@/lib/api";
import { when } from "@/lib/format";
import { useMe } from "@/lib/me";
import { cn } from "@/lib/utils";

const COLLECT: Record<Connection["collect_status"], { label: string; tone: Tone; pulse?: boolean }> = {
  never: { label: "Not read yet", tone: "neutral" },
  queued: { label: "Waiting to read", tone: "info", pulse: true },
  running: { label: "Reading", tone: "info", pulse: true },
  done: { label: "Read", tone: "success" },
  failed: { label: "Could not read", tone: "danger" },
};

// Each warehouse gets its own mark, so a list of connections scans at a glance.
const KIND_STYLE: Record<string, { icon: typeof Database; tile: string }> = {
  snowflake: { icon: Snowflake, tile: "bg-info-soft text-info-soft-foreground" },
  databricks: { icon: Layers, tile: "bg-danger-soft text-danger-soft-foreground" },
  sqlserver: { icon: Server, tile: "bg-primary-soft text-primary" },
  oracle: { icon: Database, tile: "bg-danger-soft text-danger-soft-foreground" },
  bigquery: { icon: BarChart3, tile: "bg-info-soft text-info-soft-foreground" },
  redshift: { icon: Warehouse, tile: "bg-warning-soft text-warning-soft-foreground" },
  saphana: { icon: Boxes, tile: "bg-primary-soft text-primary" },
  postgres: { icon: Database, tile: "bg-primary-soft text-primary" },
  teradata: { icon: Building2, tile: "bg-warning-soft text-warning-soft-foreground" },
  mysql: { icon: Database, tile: "bg-success-soft text-success-soft-foreground" },
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
    <>
      <PageHeader title="Connections" description="Warehouses Nexus reads, only ever with read-only queries."
        actions={manage && <Button onClick={open}><Plus />Add a connection</Button>} />

      {conns === null ? null : conns.length === 0 ? (
        <Card>
          <EmptyState icon={Cable} title="No connections yet"
            description={<>Connect Snowflake, Databricks or Postgres. To try Nexus without a warehouse, run <code>uv run nexus-seed-demo --email {me.user.email}</code> in <code>services/api</code>.</>}
            action={manage && <Button onClick={open}><Plus />Add a connection</Button>} />
        </Card>
      ) : (
        <div className="grid gap-4 lg:grid-cols-2">
          {conns.map((c) => {
            const status = COLLECT[c.collect_status];
            const result = tests[c.id];
            const style = KIND_STYLE[c.kind] ?? KIND_STYLE.postgres;
            const Icon = style.icon;
            const reading = c.collect_status === "queued" || c.collect_status === "running";
            const testOk = result ? result.ok : c.last_test_ok;
            const testMsg = result ? result.message : c.last_test_msg;
            return (
              <Card key={c.id} className="flex flex-col">
                <div className="flex items-start justify-between gap-3 px-5 pt-5">
                  <div className="flex min-w-0 items-start gap-3">
                    <div className={cn("rounded-lg p-2.5", style.tile)}><Icon className="size-5" /></div>
                    <div className="min-w-0">
                      <p className="truncate text-h2 text-foreground">{c.label}</p>
                      <p className="truncate text-caption text-muted-foreground">
                        {specs.find((s) => s.kind === c.kind)?.name ?? c.kind}
                        {c.config.database ? ` · ${c.config.database}` : ""}{c.config.host ? ` · ${c.config.host}` : ""}
                      </p>
                    </div>
                  </div>
                  <StatusPill tone={status.tone} pulse={status.pulse} dot={!status.pulse}>{status.label}</StatusPill>
                </div>
                <div className="flex-1 space-y-3 px-5 py-4">
                  {c.collect_msg && (
                    <p className="text-body text-muted-foreground">{c.collect_msg}{c.collected_at ? <span className="text-caption"> · {when(c.collected_at)}</span> : ""}</p>
                  )}
                  {testMsg && <Callout tone={testOk ? "success" : "danger"}>{testMsg}</Callout>}
                  {!c.verified && <p className="text-caption text-muted-foreground">This connector has not yet been tested against a real account.</p>}
                </div>
                {manage && (
                  <div className="flex items-center justify-end gap-2 border-t border-border bg-muted/30 px-5 py-3">
                    <Button variant="ghost" size="sm" className="mr-auto hover:text-danger" onClick={() => remove(c)}><Trash2 />Remove</Button>
                    <Button variant="outline" size="sm" disabled={busy === c.id} onClick={() => test(c)}>
                      {busy === c.id ? <Loader2 className="animate-spin" /> : <Zap />}Test
                    </Button>
                    <Button size="sm" disabled={reading} onClick={() => collect(c)}>
                      <RefreshCw className={cn(reading && "animate-spin")} />{reading ? "Reading…" : "Read tables"}
                    </Button>
                  </div>
                )}
              </Card>
            );
          })}
        </div>
      )}

      {conns && conns.some((c) => c.collect_status === "done") && (
        <Link href="/knowledge" className="group flex items-center justify-between rounded-lg border border-primary/20 bg-primary-soft px-5 py-4 text-primary">
          <span className="text-body font-medium">Everything Nexus reads arrives as a proposal. Review it in the knowledge graph.</span>
          <ArrowRight className="size-4 transition-transform group-hover:translate-x-0.5" />
        </Link>
      )}

      <Dialog ref={dialog} wide title="Add a connection" description="Credentials are encrypted and never shown again.">
        <form className="space-y-4" onSubmit={add}>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-5">
            {specs.map((s) => {
              const st = KIND_STYLE[s.kind] ?? KIND_STYLE.postgres;
              const I = st.icon;
              return (
                <button type="button" key={s.kind} onClick={() => { setKind(s.kind); setValues({}); }}
                  className={cn("flex flex-col items-center gap-1.5 rounded-lg border px-1.5 py-2.5 text-center text-caption font-medium leading-tight transition-colors",
                    kind === s.kind ? "border-primary bg-primary-soft text-primary" : "border-border text-muted-foreground hover:bg-muted/50")}>
                  <span className={cn("rounded-md p-1.5", st.tile)}><I className="size-4" /></span>{s.name.split(" / ")[0]}
                </button>
              );
            })}
          </div>
          {spec && <p className="text-caption text-muted-foreground">{spec.description}</p>}
          <Field label="Name"><Input required value={label} onChange={(e) => setLabel(e.target.value)} placeholder="Sales warehouse" /></Field>
          {spec?.fields.map((f) => (
            <Field key={f.name} label={f.label} optional={!f.required} hint={f.help || undefined}>
              {f.options.length ? (
                <Select value={values[f.name] ?? f.default} onChange={(e) => setValues({ ...values, [f.name]: e.target.value })}>
                  {f.options.map((o) => <option key={o} value={o}>{o}</option>)}
                </Select>
              ) : f.multiline ? (
                <Textarea rows={4} className="font-mono text-caption" value={values[f.name] ?? ""} onChange={(e) => setValues({ ...values, [f.name]: e.target.value })} />
              ) : (
                <Input type={f.secret ? "password" : "text"} required={f.required} placeholder={f.placeholder || f.default}
                  autoComplete="off" value={values[f.name] ?? ""} onChange={(e) => setValues({ ...values, [f.name]: e.target.value })} />
              )}
            </Field>
          ))}
          {error && <Callout tone="danger">{error}</Callout>}
          <div className="flex justify-end gap-2 pt-1">
            <Button type="button" variant="ghost" onClick={() => dialog.current?.close()}>Cancel</Button>
            <Button>Add connection</Button>
          </div>
        </form>
      </Dialog>
    </>
  );
}

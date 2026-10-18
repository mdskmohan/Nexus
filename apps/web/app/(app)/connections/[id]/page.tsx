"use client";

import Link from "next/link";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import {
  ArrowLeft, ArrowRight, CheckCircle2, Columns3, Eye, GitMerge, KeyRound, Layers, Loader2, Pencil, Play, Settings2,
  Table2, Trash2, XCircle, Zap,
} from "lucide-react";
import { ConnectionSheet } from "@/components/connections/connection-sheet";
import { KindMark, VerifiedBadge } from "@/components/connections/kinds";
import { announceRunStarted, RUN_FINISHED } from "@/components/connections/run-watcher";
import { FAILURE_TITLE, isActive, PHASE_LABEL, RunProgress, RunStatusPill } from "@/components/connections/run-ui";
import { RunsTable, type RunFilter } from "@/components/connections/runs-table";
import { Button } from "@/components/ui/button";
import { Callout } from "@/components/ui/callout";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { StatCard } from "@/components/ui/stat-card";
import { useToast } from "@/components/ui/toast";
import { api, ApiError, can, type Connection, type ConnectorSpec } from "@/lib/api";
import { useCrumb } from "@/lib/crumbs";
import { when } from "@/lib/format";
import { useMe } from "@/lib/me";

type TestResult = { ok: boolean; message: string; details: Record<string, string> };

export default function ConnectionPage() {
  return <Suspense><ConnectionDetail /></Suspense>;
}

function ConnectionDetail() {
  const { id } = useParams<{ id: string }>();
  const isNew = useSearchParams().get("new") === "1";
  const me = useMe();
  const manage = can(me, "manage_connections");
  const router = useRouter();
  const toast = useToast();
  const [conn, setConn] = useState<Connection | null>(null);
  const [missing, setMissing] = useState(false);
  const [spec, setSpec] = useState<ConnectorSpec | null>(null);
  const [specs, setSpecs] = useState<ConnectorSpec[]>([]);
  const [test, setTest] = useState<TestResult | null>(null);
  const [testing, setTesting] = useState(false);
  const [starting, setStarting] = useState(false);
  const [editing, setEditing] = useState(false);
  const [filter, setFilter] = useState<RunFilter>("all");
  const [refresh, setRefresh] = useState(0);
  const testedNew = useRef(false);
  useCrumb(`/connections/${id}`, conn?.label);

  const load = useCallback(() => api.get<Connection>(`/connections/${id}`).then(setConn).catch((e) => {
    if (e instanceof ApiError && e.status === 404) setMissing(true);
  }), [id]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    api.get<ConnectorSpec[]>("/connections/kinds").then((all) => { setSpecs(all); });
  }, []);
  useEffect(() => { if (conn) setSpec(specs.find((s) => s.kind === conn.kind) ?? null); }, [conn, specs]);
  const active = isActive(conn?.last_run);
  useEffect(() => {
    const t = setInterval(load, active ? 2000 : 15000);
    return () => clearInterval(t);
  }, [load, active]);
  useEffect(() => {
    const refresh = () => load();
    window.addEventListener(RUN_FINISHED, refresh);
    return () => window.removeEventListener(RUN_FINISHED, refresh);
  }, [load]);

  const runTest = useCallback(async () => {
    setTesting(true);
    try { setTest(await api.post<TestResult>(`/connections/${id}/test`)); load(); }
    catch (err) { toast({ tone: "danger", title: "Could not test", description: (err as Error).message }); }
    finally { setTesting(false); }
  }, [id, load, toast]);

  // A connection that was just added is tested at once, so the next step is clear.
  useEffect(() => {
    if (isNew && manage && conn && !testedNew.current) {
      testedNew.current = true;
      router.replace(`/connections/${id}`, { scroll: false });
      runTest();
    }
  }, [isNew, manage, conn, id, router, runTest]);

  async function start() {
    setStarting(true);
    try {
      const { run_id } = await api.post<{ run_id: string }>(`/connections/${id}/collect`);
      announceRunStarted(run_id);
      router.push(`/connections/runs/${run_id}`);
    } catch (err) {
      toast({ tone: "danger", title: "Could not start a run", description: (err as Error).message });
      setStarting(false);
    }
  }

  async function remove() {
    if (!conn || !confirm(`Remove ${conn.label}? Its run history is removed with it.`)) return;
    try {
      await api.del(`/connections/${id}`);
      toast({ tone: "success", title: `${conn.label} removed` });
      router.push("/connections");
    } catch (err) { toast({ tone: "danger", title: "Could not remove", description: (err as Error).message }); }
  }

  if (missing) {
    return (
      <Card><CardBody className="space-y-3 py-10 text-center">
        <p className="text-h2 text-foreground">This connection no longer exists.</p>
        <Link href="/connections" className="text-body font-medium text-primary hover:underline">Back to connections</Link>
      </CardBody></Card>
    );
  }
  if (!conn) return <div className="flex items-center gap-2 py-10 text-body text-muted-foreground"><Loader2 className="size-4 animate-spin" />Loading…</div>;

  const run = conn.last_run;
  const stats = conn.last_success?.stats;
  const testOk = test ? test.ok : conn.last_test_ok;
  const testMsg = test ? test.message : conn.last_test_msg;
  const settings = (spec?.fields ?? []).filter((f) => !f.secret && conn.config[f.name]);
  const secrets = (spec?.fields ?? []).filter((f) => f.secret);

  return (
    <>
      <Link href="/connections" className="inline-flex items-center gap-1.5 text-caption text-muted-foreground hover:text-foreground">
        <ArrowLeft className="size-3.5" />Connections
      </Link>

      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="flex min-w-0 items-start gap-4">
          <KindMark kind={conn.kind} size="lg" />
          <div className="min-w-0 space-y-1">
            <div className="flex flex-wrap items-center gap-2">
              <h1 className="truncate text-h1 tracking-tight text-foreground">{conn.label}</h1>
              <VerifiedBadge verified={conn.verified} />
            </div>
            <p className="text-body text-muted-foreground">
              {spec?.name ?? conn.kind}{conn.config.host ? ` · ${conn.config.host}` : ""}{conn.config.database ? ` · ${conn.config.database}` : ""}
              <span className="text-caption"> · added {when(conn.created_at)}</span>
            </p>
          </div>
        </div>
        {manage && (
          <div className="flex shrink-0 flex-wrap items-center gap-2">
            <Button variant="ghost" size="sm" className="hover:text-danger" onClick={remove}><Trash2 />Remove</Button>
            <Button variant="outline" size="sm" onClick={() => setEditing(true)}><Pencil />Edit</Button>
            <Button variant="outline" size="sm" disabled={testing} onClick={runTest}>{testing ? <Loader2 className="animate-spin" /> : <Zap />}Test</Button>
            <Button size="sm" disabled={active || starting} onClick={start}>
              {active || starting ? <Loader2 className="animate-spin" /> : <Play />}{active ? "Running" : "Run now"}
            </Button>
          </div>
        )}
      </div>

      {run && active && (
        <Link href={`/connections/runs/${run.id}`} className="block">
          <Card className="space-y-2 p-4 transition-shadow hover:shadow-md">
            <div className="flex items-center justify-between gap-3">
              <div className="flex items-center gap-2.5">
                <RunStatusPill run={run} />
                <span className="text-body text-foreground">{run.cancel_requested ? "Stopping…" : PHASE_LABEL[run.phase]}</span>
              </div>
              <span className="flex items-center gap-1 text-caption font-medium text-primary">Watch live<ArrowRight className="size-3.5" /></span>
            </div>
            <RunProgress run={run} />
          </Card>
        </Link>
      )}
      {run?.status === "failed" && (
        <Callout tone="danger" title={`Last run failed: ${FAILURE_TITLE[run.error_kind ?? "warehouse"]}`}
          action={<Link href={`/connections/runs/${run.id}`} className="shrink-0 self-center text-caption font-medium underline underline-offset-2">See the log</Link>}>
          {run.hint}
        </Callout>
      )}

      <div className="grid gap-3 sm:grid-cols-3 lg:grid-cols-6">
        <StatCard label="Schemas" value={stats?.schemas ?? "–"} icon={Layers} />
        <StatCard label="Tables" value={stats?.tables ?? "–"} icon={Table2} tone="primary" />
        <StatCard label="Views" value={stats?.views ?? "–"} icon={Eye} />
        <StatCard label="Columns" value={stats?.columns ?? "–"} icon={Columns3} />
        <StatCard label="Foreign keys" value={stats?.foreign_keys ?? "–"} icon={KeyRound} />
        <StatCard label="Joins suggested" value={stats?.joins_suggested ?? "–"} icon={GitMerge} tone="success" />
      </div>
      <p className="-mt-3 text-caption text-muted-foreground">
        {conn.last_success ? <>From the last successful run, {when(conn.last_success.finished_at)}. <Link href={`/connections/runs/${conn.last_success.id}`} className="text-primary hover:underline">Open it</Link></>
          : "Nothing read yet. Counts appear after the first successful run."}
      </p>

      <div className="grid gap-4 lg:grid-cols-[1fr_1.4fr]">
        <Card>
          <CardHeader icon={<Settings2 />} title="Settings" description="Secrets are encrypted and never shown."
            actions={manage && <Button variant="ghost" size="sm" onClick={() => setEditing(true)}><Pencil />Edit</Button>} />
          <dl className="divide-y divide-border">
            {settings.map((f) => (
              <div key={f.name} className="grid grid-cols-[minmax(0,2fr)_minmax(0,3fr)] gap-3 px-5 py-2.5">
                <dt className="text-caption text-muted-foreground">{f.label}</dt>
                <dd className="truncate font-mono text-caption text-foreground" title={conn.config[f.name]}>{conn.config[f.name]}</dd>
              </div>
            ))}
            {secrets.map((f) => (
              <div key={f.name} className="grid grid-cols-[minmax(0,2fr)_minmax(0,3fr)] gap-3 px-5 py-2.5">
                <dt className="text-caption text-muted-foreground">{f.label}</dt>
                <dd className="text-caption">{conn.secrets_saved.includes(f.name)
                  ? <span className="text-foreground">•••••••• saved</span> : <span className="text-muted-foreground">Not set</span>}</dd>
              </div>
            ))}
          </dl>
        </Card>

        <Card>
          <CardHeader icon={<Zap />} title="Connection test"
            description={conn.last_test_at ? `Last tested ${when(test ? new Date().toISOString() : conn.last_test_at)}` : "Not tested yet"}
            actions={manage && <Button variant="outline" size="sm" disabled={testing} onClick={runTest}>{testing ? <Loader2 className="animate-spin" /> : <Zap />}Test now</Button>} />
          <CardBody className="space-y-3">
            {testing ? (
              <p className="flex items-center gap-2 text-body text-muted-foreground"><Loader2 className="size-4 animate-spin" />Testing each step…</p>
            ) : testMsg ? (
              <Callout tone={testOk ? "success" : "danger"} title={testOk ? "The connection works" : "The test failed"}>{testMsg}</Callout>
            ) : (
              <p className="text-body text-muted-foreground">Test the connection to check that Nexus can sign in and see tables.</p>
            )}
            {test && Object.keys(test.details).length > 0 && (
              <ul className="divide-y divide-border rounded-md border border-border">
                {Object.entries(test.details).map(([step, result]) => {
                  const passed = result === "passed";
                  return (
                    <li key={step} className="flex items-start gap-2.5 px-3 py-2 text-body">
                      {passed ? <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-success" />
                        : result.startsWith("failed") || result.startsWith("Failed") ? <XCircle className="mt-0.5 size-4 shrink-0 text-danger" />
                        : <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-muted-foreground" />}
                      <span className="min-w-0 flex-1 text-foreground">{step}</span>
                      <span className="max-w-[55%] truncate text-caption text-muted-foreground" title={result}>{result}</span>
                    </li>
                  );
                })}
              </ul>
            )}
            {test?.ok && !run && manage && (
              <Button onClick={start} disabled={starting}>{starting ? <Loader2 className="animate-spin" /> : <Play />}Run it now to read the tables</Button>
            )}
          </CardBody>
        </Card>
      </div>

      <div className="space-y-3">
        <h2 className="text-h2 text-foreground">Runs</h2>
        <RunsTable connectionId={id} filter={filter} onFilter={setFilter} refreshKey={refresh} />
      </div>

      {manage && (
        <ConnectionSheet open={editing} specs={specs} editing={conn} onClose={() => setEditing(false)}
          onSaved={() => { toast({ tone: "success", title: "Settings saved", description: "Test the connection to check them." }); setTest(null); load(); setRefresh((n) => n + 1); }} />
      )}
    </>
  );
}

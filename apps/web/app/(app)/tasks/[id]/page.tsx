"use client";

import Link from "next/link";
import { use, useCallback, useEffect, useState } from "react";
import { api, atLeast, type Run } from "@/lib/api";
import { duration, RUN_STATUS, when } from "@/lib/format";
import { useMe } from "@/lib/me";
import AskResult from "@/components/task/AskResult";
import DraftResult from "@/components/task/DraftResult";
import ReviewResult from "@/components/task/ReviewResult";
import SafetyChecks from "@/components/task/SafetyChecks";
import Timeline from "@/components/task/Timeline";

const KIND = { ask: "Question", review: "Contract review", draft: "Drafting" } as const;

export default function TaskPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const me = useMe();
  const [run, setRun] = useState<Run | null>(null);
  const [missing, setMissing] = useState(false);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => api.get<Run>(`/runs/${id}`).then(setRun).catch(() => setMissing(true)), [id]);
  useEffect(() => { load(); }, [load]);

  const live = run?.status === "queued" || run?.status === "running";
  useEffect(() => {
    if (!live) return;
    const t = setInterval(load, 1500);
    return () => clearInterval(t);
  }, [live, load]);

  async function stop() {
    if (!confirm("Stop this task? What the AI has done so far is kept in the activity record.")) return;
    await api.post(`/runs/${id}/cancel`);
    await load();
  }

  async function decide(action: "approve" | "reject") {
    setBusy(true);
    try {
      await api.post(`/runs/${id}/${action}`, { note });
      setNote("");
      await load();
    } finally {
      setBusy(false);
    }
  }

  if (missing) return <div className="empty">This task does not exist, or you do not have access to it.</div>;
  if (!run) return <div className="empty">Loading…</div>;

  const status = RUN_STATUS[run.status];
  const canDecide = atLeast(me.user.role, "associate") && ["needs_review", "approved", "rejected"].includes(run.status);

  return (
    <>
      <div className="page-head">
        <div style={{ minWidth: 0 }}>
          <div className="faint"><Link href={`/matters/${run.matter_id}`}>{run.matter_name}</Link> · {KIND[run.kind]}</div>
          <h1 style={{ fontSize: 24 }}>{run.kind === "ask" ? run.input?.question : run.title}</h1>
          {run.kind === "draft" && run.input?.instructions && <p className="muted" style={{ marginTop: 6 }}>{run.input.instructions}</p>}
          <div className="row" style={{ marginTop: 10 }}>
            <span className={status.tone}>{status.label}</span>
            <span className="faint">
              Started {when(run.created_at)}{run.created_by_name ? ` by ${run.created_by_name}` : ""}
              {run.started_at && ` · ${live ? "working for" : "took"} ${duration(run.started_at, run.finished_at)}`}
            </span>
          </div>
        </div>
      </div>

      {run.status === "failed" && (
        <div className="notice notice-bad" style={{ marginBottom: 20 }}><p><strong>This task did not finish.</strong> {run.error}</p></div>
      )}
      {run.status === "cancelled" && (
        <div className="notice notice-info" style={{ marginBottom: 20 }}><p>{run.error}</p></div>
      )}
      {run.status === "approved" && (
        <div className="notice notice-ok" style={{ marginBottom: 20 }}>
          <p>Approved by {run.reviewed_by_name} {when(run.reviewed_at)}.{run.review_note ? ` “${run.review_note}”` : ""}</p>
        </div>
      )}
      {run.status === "rejected" && (
        <div className="notice notice-bad" style={{ marginBottom: 20 }}>
          <p>Sent back by {run.reviewed_by_name} {when(run.reviewed_at)}.{run.review_note ? ` “${run.review_note}”` : ""}</p>
        </div>
      )}

      <div className="grid-2">
        <div className="stack">
          {live && (
            <div className="card card-pad row" style={{ justifyContent: "space-between" }}>
              <p className="muted">The AI is working. You can leave this page; the result will be in the matter&apos;s history.</p>
              <button className="btn-small" onClick={stop}>Stop task</button>
            </div>
          )}
          {run.output && run.kind === "ask" && <AskResult output={run.output} />}
          {run.output && run.kind === "review" && <ReviewResult output={run.output} files={run.files ?? []} />}
          {run.output && run.kind === "draft" && <DraftResult output={run.output} files={run.files ?? []} />}

          {canDecide && (
            <div className="card card-pad stack">
              <h3>Your sign-off</h3>
              <p className="muted">AI work stays a draft until someone at the firm approves it. Your decision is recorded in the audit trail.</p>
              <label>Note <span className="hint">Optional</span>
                <textarea rows={2} value={note} onChange={(e) => setNote(e.target.value)} placeholder="e.g. Checked against the signed version." />
              </label>
              <div className="row">
                <button className="btn-ok" disabled={busy} onClick={() => decide("approve")}>Approve</button>
                <button disabled={busy} onClick={() => decide("reject")}>Send back</button>
              </div>
            </div>
          )}
        </div>

        <div className="stack">
          <SafetyChecks run={run} />
          <div className="card">
            <div className="card-head"><h3>What the AI did</h3>{live && <span className="pill pill-brand">Live</span>}</div>
            <div className="card-pad" style={{ paddingTop: 8 }}>
              <Timeline steps={run.steps ?? []} live={live} />
            </div>
          </div>
        </div>
      </div>
    </>
  );
}

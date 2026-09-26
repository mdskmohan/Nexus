"use client";

import { useState } from "react";
import type { Step } from "@/lib/api";

// Plain-language steps for everyone; the raw record behind each step is one
// click away for whoever supports the firm's systems.
export default function Timeline({ steps, live }: { steps: Step[]; live: boolean }) {
  const [technical, setTechnical] = useState(false);
  const [open, setOpen] = useState<number | null>(null);
  if (!steps.length) {
    return <p className="faint">{live ? "Starting…" : "No steps were recorded."}</p>;
  }
  return (
    <>
      <ol className="timeline">
        {steps.map((s) => (
          <li key={s.seq}>
            <span className={`dot ${s.status}`} />
            <div>
              {technical ? (
                <button className="btn-quiet" style={{ padding: 0, fontWeight: 500, color: "var(--ink)", whiteSpace: "normal", textAlign: "left" }}
                        onClick={() => setOpen(open === s.seq ? null : s.seq)} aria-expanded={open === s.seq}>
                  {s.title}
                </button>
              ) : (
                <span>{s.title}</span>
              )}
              {technical && open === s.seq && (
                <pre className="mono" style={{ whiteSpace: "pre-wrap", background: "var(--surface-2)", padding: 10, borderRadius: 8, marginTop: 6, maxHeight: 260, overflow: "auto" }}>
                  {JSON.stringify({ kind: s.kind, duration_ms: s.duration_ms, ...s.detail }, null, 2)}
                </pre>
              )}
            </div>
          </li>
        ))}
        {live && (
          <li><span className="dot live" /><span className="muted">Working…</span></li>
        )}
      </ol>
      <button className="btn-quiet btn-small" style={{ padding: 0, marginTop: 8 }} onClick={() => setTechnical(!technical)}>
        {technical ? "Hide technical details" : "Show technical details"}
      </button>
    </>
  );
}

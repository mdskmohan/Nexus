"use client";

import { useState } from "react";
import type { Finding, ReviewOutput } from "@/lib/api";
import Source from "./Source";

const STATUS: Record<Finding["status"], { label: string; tone: string }> = {
  meets: { label: "Meets standard", tone: "pill pill-ok" },
  deviates: { label: "Deviates", tone: "pill pill-bad" },
  missing: { label: "Missing", tone: "pill pill-bad" },
  unclear: { label: "Your judgement", tone: "pill pill-warn" },
};
const RISK: Record<Finding["risk"], string> = { high: "High risk", medium: "Medium", low: "Low" };

function FindingCard({ f }: { f: Finding }) {
  const [copied, setCopied] = useState(false);
  return (
    <div className="card card-pad stack" style={{ gap: 10 }}>
      <div className="row" style={{ justifyContent: "space-between" }}>
        <h3>{f.title}</h3>
        <div className="row" style={{ gap: 6 }}>
          <span className={STATUS[f.status].tone}>{STATUS[f.status].label}</span>
          {f.status !== "meets" && <span className={`pill ${f.risk === "high" ? "pill-bad" : ""}`}>{RISK[f.risk]}</span>}
        </div>
      </div>
      <p>{f.explanation}</p>
      {f.citation && <Source c={f.citation} />}
      {f.suggested_language && (
        <div className="stack" style={{ gap: 6 }}>
          <div className="row" style={{ justifyContent: "space-between" }}>
            <span className="faint"><strong>{f.status === "missing" ? "Suggested addition" : "Suggested wording"}</strong></span>
            <button className="btn-quiet btn-small" onClick={() => { navigator.clipboard.writeText(f.suggested_language); setCopied(true); }}>
              {copied ? "Copied" : "Copy"}
            </button>
          </div>
          <p style={{ fontFamily: "var(--font-serif)", background: "var(--surface-2)", padding: "10px 14px", borderRadius: 8 }}>{f.suggested_language}</p>
        </div>
      )}
    </div>
  );
}

export default function ReviewResult({ output, files }: { output: ReviewOutput; files: { id: string; filename: string }[] }) {
  const [showAll, setShowAll] = useState(false);
  const [copied, setCopied] = useState(false);
  const counts = { meets: 0, deviates: 0, missing: 0, unclear: 0 };
  output.findings.forEach((f) => counts[f.status]++);
  const shown = showAll ? output.findings : output.issues;

  return (
    <>
      <div className="card card-pad stack">
        <h2>Summary</h2>
        <div className="row" style={{ gap: 8 }}>
          <span className="pill pill-ok">{counts.meets} meet the standard</span>
          <span className="pill pill-bad">{counts.deviates} deviate</span>
          <span className="pill pill-bad">{counts.missing} missing</span>
          <span className="pill pill-warn">{counts.unclear} for your judgement</span>
        </div>
        <p className="pre">{output.summary}</p>
        {files.length > 0 && (
          <div className="stack" style={{ gap: 8 }}>
            <span className="faint"><strong>Word files</strong></span>
            <div className="row">
              {files.map((f) => <a key={f.id} className="btn" href={`/api/files/${f.id}`}>{f.filename}</a>)}
            </div>
            {output.redline_not_placed?.length ? (
              <p className="faint">Could not place in the Word copy (see the memo instead): {output.redline_not_placed.join(", ")}.</p>
            ) : null}
          </div>
        )}
      </div>

      <div className="row" style={{ justifyContent: "space-between" }}>
        <h2>{showAll ? "All findings" : `Issues (${output.issues.length})`}</h2>
        <button className="btn-quiet btn-small" onClick={() => setShowAll(!showAll)}>
          {showAll ? "Show issues only" : `Show all ${output.findings.length} points`}
        </button>
      </div>
      {shown.map((f) => <FindingCard key={f.position_id} f={f} />)}

      <div className="card card-pad stack">
        <div className="row" style={{ justifyContent: "space-between" }}>
          <h3>Draft note to the client</h3>
          <button className="btn-quiet btn-small" onClick={() => { navigator.clipboard.writeText(output.client_note); setCopied(true); }}>
            {copied ? "Copied" : "Copy"}
          </button>
        </div>
        <p className="pre">{output.client_note}</p>
      </div>
    </>
  );
}

"use client";

import type { DraftOutput } from "@/lib/api";
import Source from "./Source";

// Shows the draft as text with its checked sources; the Word/Excel files are
// the deliverable and are downloaded from the buttons at the top.
export default function DraftResult({ output, files }: { output: DraftOutput; files: { id: string; filename: string }[] }) {
  return (
    <>
      <div className="card card-pad stack">
        <h2>Draft ready</h2>
        {output.summary && <p>{output.summary}</p>}
        <div className="row">
          {files.map((f) => <a key={f.id} className="btn btn-primary" href={`/api/files/${f.id}`}>Download {f.filename}</a>)}
        </div>
      </div>
      {output.deliverables.map((d) => (
        <div key={d.filename} className="card card-pad stack">
          <div className="row" style={{ justifyContent: "space-between" }}>
            <h3>{d.filename}</h3>
            {d.unverified.length > 0
              ? <span className="pill pill-warn">{d.unverified.length} unverified</span>
              : <span className="pill pill-ok">All sources checked</span>}
          </div>
          <div className="pre" style={{ fontFamily: "var(--font-serif)", maxHeight: 480, overflow: "auto", background: "var(--surface-2)", padding: 16, borderRadius: 8 }}>
            {d.content}
          </div>
          {d.sources.filter((s) => s.verified).length > 0 && (
            <details>
              <summary className="faint" style={{ cursor: "pointer" }}>Sources ({d.sources.filter((s) => s.verified).length})</summary>
              <div className="stack" style={{ gap: 10, marginTop: 10 }}>
                {d.sources.filter((s) => s.verified).map((s) => <Source key={s.id} c={s} label={s.id} />)}
              </div>
            </details>
          )}
        </div>
      ))}
    </>
  );
}

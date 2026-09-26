"use client";

import { useState } from "react";
import type { AskOutput } from "@/lib/api";
import Source from "./Source";

export default function AskResult({ output }: { output: AskOutput }) {
  const [active, setActive] = useState<number | null>(null);
  const sources = output.answer.flatMap((s) => s.citations);
  let n = 0;

  function show(i: number) {
    setActive(i);
    document.getElementById(`source-${i}`)?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  return (
    <>
      <div className="card card-pad stack answer">
        <h2>Answer</h2>
        {output.answer.length === 0 && <p className="muted">The documents do not answer this question.</p>}
        <div>
          {output.answer.map((s, i) => (
            <p key={i} className="statement">
              {s.text}
              {s.citations.map((_, j) => {
                const k = ++n;
                return (
                  <button key={j} className="cite" onClick={() => show(k)} aria-label={`Source ${k}`}>{k}</button>
                );
              })}
            </p>
          ))}
        </div>
        {output.could_not_answer && (
          <div className="notice notice-info">
            <p><strong>Not covered by the documents:</strong> {output.could_not_answer}</p>
          </div>
        )}
      </div>

      {sources.length > 0 && (
        <div className="card card-pad stack" style={{ gap: 12 }}>
          <h3>Sources</h3>
          {sources.map((c, i) => <Source key={i} n={i + 1} c={c} id={`source-${i + 1}`} active={active === i + 1} />)}
        </div>
      )}

      {output.removed.length > 0 && (
        <div className="card card-pad stack" style={{ gap: 10 }}>
          <h3>Removed before you saw them</h3>
          <p className="muted">These statements were in the AI&apos;s draft, but their quotes could not be found in the documents, so they are not part of the answer.</p>
          {output.removed.map((r, i) => (
            <div key={i} className="notice notice-warn">
              <div><p style={{ textDecoration: "line-through" }}>{r.text}</p><p className="faint" style={{ color: "inherit" }}>{r.reason}</p></div>
            </div>
          ))}
        </div>
      )}
    </>
  );
}

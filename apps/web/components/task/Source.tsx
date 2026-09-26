"use client";

import type { Citation } from "@/lib/api";

export function where(c: Citation): string {
  const parts = [c.document ?? "Document"];
  if (c.location) parts.push(c.location);
  if (c.heading) parts.push(c.heading);
  return parts.join(" · ");
}

export default function Source({ n, c, active, id, label }: { n?: number; c: Citation; active?: boolean; id?: string; label?: string }) {
  return (
    <div className={`source ${active ? "active" : ""}`} id={id}>
      <div className="row" style={{ justifyContent: "space-between", gap: 8 }}>
        <span className="faint">{n !== undefined && <strong>[{n}] </strong>}{label && <strong>{label} · </strong>}{where(c)}</span>
        {c.verified ? <span className="pill pill-ok">✓ Checked</span> : <span className="pill pill-bad">Not verified</span>}
      </div>
      <blockquote>&ldquo;{c.quote}&rdquo;</blockquote>
      {c.document_id && (
        <a className="faint" href={`/api/documents/${c.document_id}/file`}>Open document</a>
      )}
    </div>
  );
}

"use client";

import { useRef, useState } from "react";
import { api, type Doc } from "@/lib/api";
import { bytes, plural, when } from "@/lib/format";
import { useMe } from "@/lib/me";
import { atLeast } from "@/lib/api";

const STATUS: Record<Doc["status"], { label: string; tone: string }> = {
  queued: { label: "Waiting", tone: "pill" },
  processing: { label: "Reading…", tone: "pill pill-brand" },
  ready: { label: "Ready", tone: "pill pill-ok" },
  failed: { label: "Could not read", tone: "pill pill-bad" },
};

export function DocWarnings({ doc }: { doc: Doc }) {
  const hidden = doc.flags?.hidden_instruction_count ?? 0;
  const sensitive = Object.entries(doc.flags?.sensitive ?? {});
  if (!hidden && !sensitive.length) return null;
  return (
    <div className="stack" style={{ gap: 8, marginTop: 8 }}>
      {hidden > 0 && (
        <div className="notice notice-warn" style={{ padding: "8px 12px" }}>
          <div>
            <p><strong>Contains text aimed at an AI.</strong> The AI will treat it as part of the document, never as an instruction.</p>
            {doc.flags.hidden_instructions?.slice(0, 2).map((h, i) => (
              <p key={i} className="faint" style={{ color: "inherit", marginTop: 4 }}>
                Page {h.page}: &ldquo;{h.excerpt}&rdquo;
              </p>
            ))}
          </div>
        </div>
      )}
      {sensitive.length > 0 && (
        <div className="notice notice-info" style={{ padding: "8px 12px" }}>
          <p>
            <strong>Sensitive numbers found:</strong>{" "}
            {sensitive.map(([k, n]) => plural(n, k)).join(", ")}. Check they belong in this file.
          </p>
        </div>
      )}
    </div>
  );
}

export default function DocumentsTab({ matterId, docs, onChange }: { matterId: string; docs: Doc[]; onChange: () => void }) {
  const me = useMe();
  const input = useRef<HTMLInputElement>(null);
  const [over, setOver] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function upload(files: FileList | null) {
    if (!files?.length) return;
    const body = new FormData();
    Array.from(files).forEach((f) => body.append("files", f));
    setBusy(true);
    setError("");
    try {
      await api.post(`/matters/${matterId}/documents`, body);
      onChange();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
      if (input.current) input.current.value = "";
    }
  }

  async function remove(doc: Doc) {
    if (!confirm(`Remove “${doc.filename}” from this matter? Earlier answers that cite it keep their quotes.`)) return;
    await api.del(`/documents/${doc.id}`);
    onChange();
  }

  return (
    <div className="stack">
      <div
        className={`drop ${over ? "over" : ""}`}
        onDragOver={(e) => { e.preventDefault(); setOver(true); }}
        onDragLeave={() => setOver(false)}
        onDrop={(e) => { e.preventDefault(); setOver(false); upload(e.dataTransfer.files); }}
      >
        <p style={{ fontWeight: 600, color: "var(--ink)" }}>Drag documents here</p>
        <p className="faint" style={{ margin: "4px 0 12px" }}>PDF, Word (.docx) or text files, up to 50 MB each. Scanned PDFs need OCR first.</p>
        <button className="btn-primary" disabled={busy} onClick={() => input.current?.click()}>
          {busy ? "Uploading…" : "Choose files"}
        </button>
        <input ref={input} type="file" multiple hidden accept=".pdf,.docx,.txt" onChange={(e) => upload(e.target.files)} />
      </div>
      {error && <div className="notice notice-bad"><p>{error}</p></div>}

      {docs.length > 0 && (
        <div className="card">
          <table>
            <thead><tr><th>Document</th><th>Status</th><th>Added</th><th></th></tr></thead>
            <tbody>
              {docs.map((d) => (
                <tr key={d.id}>
                  <td>
                    <a href={`/api/documents/${d.id}/file`} style={{ fontWeight: 600 }}>{d.filename}</a>
                    <div className="faint">
                      {bytes(d.size_bytes)}
                      {d.page_count && d.content_type === "application/pdf" ? ` · ${plural(d.page_count, "page")}` : ""}
                    </div>
                    {d.status === "failed" && d.error && <p className="faint" style={{ color: "var(--bad)", marginTop: 4 }}>{d.error}</p>}
                    <DocWarnings doc={d} />
                  </td>
                  <td><span className={STATUS[d.status].tone}>{STATUS[d.status].label}</span></td>
                  <td className="muted">{when(d.created_at)}{d.uploaded_by ? ` by ${d.uploaded_by}` : ""}</td>
                  <td style={{ textAlign: "right" }}>
                    {atLeast(me.user.role, "associate") && (
                      <button className="btn-quiet btn-small" onClick={() => remove(d)}>Remove</button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { api, type Doc } from "@/lib/api";
import ModelPicker from "@/components/ModelPicker";

const TEMPLATES = [
  {
    label: "List of dates and events",
    file: "list-of-dates.docx",
    text: "Prepare a List of Dates and Events from all documents in this matter, in the form used in Indian court filings (for example with a Special Leave Petition or an appeal). Use a table with two columns, Date and Event, in chronological order. Include every date that matters to the dispute: agreements, notices, payments, correspondence, orders and filings. Write each event in one or two neutral, factual sentences, and give every event a source. Where a document gives only a month or year, say so. Where documents give conflicting dates, list both and note the conflict. Do not add argument.",
  },
  {
    label: "Issues memo",
    file: "issues-memo.docx",
    text: "Review all documents in this matter and prepare an issues memo for the supervising partner. For each issue: what it is, where it comes from, why it matters, and what we recommend. End with a short list of open questions for the client.",
  },
  {
    label: "Contract summary schedule",
    file: "contract-summary.xlsx",
    text: "Prepare a schedule summarising every agreement in this matter: parties, date, term and renewal, termination rights, change of control, assignment, governing law, and anything unusual.",
  },
  {
    label: "Client update email",
    file: "client-update.docx",
    text: "Draft a short email to the client summarising where things stand on this matter, the key risks, and what we need from them. Plain English, no more than one page.",
  },
];

export default function DraftTab({ matterId, readyDocs, onGoToDocuments }: {
  matterId: string; readyDocs: Doc[]; onGoToDocuments: () => void;
}) {
  const router = useRouter();
  const [instructions, setInstructions] = useState("");
  const [file, setFile] = useState("draft.docx");
  const [modelId, setModelId] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function start(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const { id } = await api.post<{ id: string }>(`/matters/${matterId}/drafts`, { instructions, deliverables: [file], model_id: modelId || null });
      router.push(`/tasks/${id}`);
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  }

  if (!readyDocs.length) {
    return (
      <div className="card empty stack" style={{ alignItems: "center" }}>
        <h2>Add documents first</h2>
        <p>Drafts are written from this matter&apos;s documents.</p>
        <button className="btn-primary" onClick={onGoToDocuments}>Add documents</button>
      </div>
    );
  }

  return (
    <div className="grid-2">
      <form className="card card-pad stack" onSubmit={start}>
        <div className="row" style={{ gap: 8 }}>
          {TEMPLATES.map((t) => (
            <button type="button" key={t.label} className="btn-small" onClick={() => { setInstructions(t.text); setFile(t.file); }}>{t.label}</button>
          ))}
        </div>
        <label>
          What should be drafted?
          <span className="hint">Brief it as you would an associate: who it is for, what it must cover, the format.</span>
          <textarea required minLength={10} rows={8} value={instructions} onChange={(e) => setInstructions(e.target.value)} />
        </label>
        <label>
          File name <span className="hint">Ends in .docx (Word), .xlsx (Excel) or .md</span>
          <input required value={file} onChange={(e) => setFile(e.target.value)} />
        </label>
        <ModelPicker value={modelId} onChange={setModelId} />
        {error && <div className="notice notice-bad"><p>{error}</p></div>}
        <div className="row"><button className="btn-primary" disabled={busy || instructions.trim().length < 10}>{busy ? "Starting…" : "Start drafting"}</button></div>
      </form>
      <div className="card card-pad stack" style={{ gap: 10 }}>
        <h3>How drafts are checked</h3>
        <p className="muted">Every fact in the draft carries a numbered source. Each source quotes the document it comes from, and Nexus checks every quote word for word.</p>
        <p className="muted">A fact whose source cannot be verified is shown as <strong>[unverified]</strong> in the draft, so you know exactly what to check.</p>
        <p className="muted">You get a Word or Excel file ready to edit, and the draft stays a draft until someone approves it.</p>
      </div>
    </div>
  );
}

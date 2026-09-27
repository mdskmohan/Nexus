"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { api, type Doc } from "@/lib/api";
import ModelPicker from "@/components/ModelPicker";

const EXAMPLES = [
  "How long do the confidentiality obligations last after the agreement ends?",
  "Can either party disclose confidential information if a court orders it?",
  "What restrictions are there on hiring the other side's employees?",
  "Which law governs the agreement, and where are disputes heard?",
];

export default function AskTab({ matterId, readyDocs, onGoToDocuments }: {
  matterId: string; readyDocs: Doc[]; onGoToDocuments: () => void;
}) {
  const router = useRouter();
  const [question, setQuestion] = useState("");
  const [modelId, setModelId] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function ask(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const { id } = await api.post<{ id: string }>(`/matters/${matterId}/ask`, { question, model_id: modelId || null });
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
        <p>Questions are answered only from this matter&apos;s documents.</p>
        <button className="btn-primary" onClick={onGoToDocuments}>Add documents</button>
      </div>
    );
  }

  return (
    <div className="grid-2">
      <form className="card card-pad stack" onSubmit={ask}>
        <label>
          Your question
          <span className="hint">Answered only from the {readyDocs.length} document{readyDocs.length === 1 ? "" : "s"} in this matter. Every statement links to the exact words it relies on.</span>
          <textarea required minLength={3} rows={5} value={question} onChange={(e) => setQuestion(e.target.value)}
                    placeholder="e.g. Can Brightline share our information with its investors?" />
        </label>
        <ModelPicker value={modelId} onChange={setModelId} />
        {error && <div className="notice notice-bad"><p>{error}</p></div>}
        <div className="row"><button className="btn-primary" disabled={busy || question.trim().length < 3}>{busy ? "Starting…" : "Ask"}</button></div>
        <div>
          <p className="faint" style={{ marginBottom: 8 }}>Examples</p>
          <div className="stack" style={{ gap: 6 }}>
            {EXAMPLES.map((q) => (
              <button type="button" key={q} className="btn-quiet btn-small" style={{ justifyContent: "flex-start", whiteSpace: "normal", textAlign: "left" }} onClick={() => setQuestion(q)}>
                {q}
              </button>
            ))}
          </div>
        </div>
      </form>
      <div className="card card-pad stack" style={{ gap: 10 }}>
        <h3>How answers are checked</h3>
        <p className="muted">The AI searches and reads the documents, then writes an answer where every statement quotes its source.</p>
        <p className="muted">Before you see it, Nexus checks each quote word for word against the document. Anything that cannot be verified is removed and listed separately.</p>
        <p className="muted">Answers are drafts until someone at the firm approves them.</p>
      </div>
    </div>
  );
}

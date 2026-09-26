"use client";

import { use, useCallback, useEffect, useState } from "react";
import { api, type Doc, type Matter, type Run } from "@/lib/api";
import AskTab from "@/components/matter/AskTab";
import DocumentsTab from "@/components/matter/DocumentsTab";
import DraftTab from "@/components/matter/DraftTab";
import HistoryTab from "@/components/matter/HistoryTab";
import ReviewTab from "@/components/matter/ReviewTab";

const TABS = [
  { id: "ask", label: "Ask a question" },
  { id: "review", label: "Review a contract" },
  { id: "draft", label: "Draft a document" },
  { id: "documents", label: "Documents" },
  { id: "history", label: "History" },
] as const;
type TabId = (typeof TABS)[number]["id"];

export default function MatterPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [matter, setMatter] = useState<Matter | null>(null);
  const [docs, setDocs] = useState<Doc[]>([]);
  const [runs, setRuns] = useState<Run[]>([]);
  const [tab, setTab] = useState<TabId | null>(null);
  const [missing, setMissing] = useState(false);

  const refresh = useCallback(async () => {
    const [d, r] = await Promise.all([
      api.get<Doc[]>(`/matters/${id}/documents`),
      api.get<Run[]>(`/matters/${id}/runs`),
    ]);
    setDocs(d);
    setRuns(r);
    return d;
  }, [id]);

  useEffect(() => {
    api.get<Matter>(`/matters/${id}`).then(setMatter).catch(() => setMissing(true));
    refresh().then((d) => setTab((t) => t ?? (d.length ? "ask" : "documents")));
  }, [id, refresh]);

  // While documents are processing, check back until they are ready.
  const processing = docs.some((d) => d.status === "queued" || d.status === "processing");
  useEffect(() => {
    if (!processing) return;
    const t = setInterval(refresh, 1500);
    return () => clearInterval(t);
  }, [processing, refresh]);

  if (missing) return <div className="empty">This matter does not exist, or you do not have access to it.</div>;
  if (!matter || !tab) return <div className="empty">Loading…</div>;

  const ready = docs.filter((d) => d.status === "ready");

  return (
    <>
      <div className="page-head">
        <div>
          <div className="faint">{matter.client_name || "No client set"}</div>
          <h1>{matter.name}</h1>
          {matter.description && <p>{matter.description}</p>}
        </div>
      </div>
      <div className="tabs" role="tablist">
        {TABS.map((t) => (
          <button key={t.id} role="tab" aria-selected={tab === t.id} className={`tab ${tab === t.id ? "active" : ""}`} onClick={() => setTab(t.id)}>
            {t.label}
            {t.id === "documents" && ` (${docs.length})`}
            {t.id === "history" && runs.length > 0 && ` (${runs.length})`}
          </button>
        ))}
      </div>
      {tab === "ask" && <AskTab matterId={id} readyDocs={ready} onGoToDocuments={() => setTab("documents")} />}
      {tab === "review" && <ReviewTab matterId={id} readyDocs={ready} onGoToDocuments={() => setTab("documents")} />}
      {tab === "draft" && <DraftTab matterId={id} readyDocs={ready} onGoToDocuments={() => setTab("documents")} />}
      {tab === "documents" && <DocumentsTab matterId={id} docs={docs} onChange={refresh} />}
      {tab === "history" && <HistoryTab runs={runs} />}
    </>
  );
}

"use client";

import { TimelineChecks } from "@/components/matter/NoticeTab";

type NoticeOutput = {
  content: string;
  checks: { ok: boolean; title: string; detail: string; source: string }[];
  facts: { amount_figures: string; amount_words: string; cheque_number: string; drawer_name: string };
};

export default function NoticeResult({ output, files }: { output: NoticeOutput; files: { id: string; filename: string }[] }) {
  return (
    <>
      <div className="card card-pad stack">
        <h2>Notice ready</h2>
        <p className="muted">Every fact you entered was checked against the text: cheque {output.facts.cheque_number}, ₹ {output.facts.amount_figures}/- ({output.facts.amount_words}), dates, bank, names, reason and the 15-day demand.</p>
        <div className="row">
          {files.map((f) => <a key={f.id} className="btn btn-primary" href={`/api/files/${f.id}`}>Download {f.filename}</a>)}
        </div>
      </div>
      <div className="card">
        <div className="card-head"><h3>Statutory timeline</h3></div>
        <div className="card-pad" style={{ paddingTop: 8 }}><TimelineChecks checks={output.checks} /></div>
      </div>
      <div className="card card-pad stack">
        <h3>The notice</h3>
        <div className="pre" style={{ fontFamily: "var(--font-serif)", background: "var(--surface-2)", padding: 16, borderRadius: 8, maxHeight: 560, overflow: "auto" }}>
          {output.content}
        </div>
      </div>
    </>
  );
}

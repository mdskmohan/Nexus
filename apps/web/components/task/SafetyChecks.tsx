"use client";

import type { Run } from "@/lib/api";
import { money, plural } from "@/lib/format";

function Check({ ok, warn, children }: { ok?: boolean; warn?: boolean; children: React.ReactNode }) {
  const tone = warn ? "var(--warn)" : ok ? "var(--ok)" : "var(--ink-3)";
  return (
    <li style={{ display: "grid", gridTemplateColumns: "20px 1fr", gap: 8, padding: "6px 0" }}>
      <span aria-hidden style={{ color: tone, fontWeight: 700 }}>{warn ? "!" : ok ? "✓" : "·"}</span>
      <span>{children}</span>
    </li>
  );
}

export default function SafetyChecks({ run }: { run: Run }) {
  const g = run.guardrails ?? {};
  const finished = !!run.output;
  const review = run.kind === "review" ? run.output : undefined;
  return (
    <div className="card">
      <div className="card-head"><h3>Safety checks</h3></div>
      <ul className="card-pad" style={{ listStyle: "none", margin: 0, paddingTop: 8 }}>
        {finished && (
          <Check ok>
            {g.citations_verified ?? 0} quotes checked word for word against the documents
          </Check>
        )}
        {finished && !!g.statements_removed && (
          <Check warn>{plural(g.statements_removed, "statement")} removed because the source could not be verified</Check>
        )}
        {finished && !!g.unverified_markers && (
          <Check warn>{plural(g.unverified_markers, "source")} could not be verified and {g.unverified_markers === 1 ? "is" : "are"} marked [unverified] in the draft</Check>
        )}
        {finished && !!g.sent_back_to_fix && (
          <Check ok>The AI was sent back to fix its work {plural(g.sent_back_to_fix, "time")} before you saw it</Check>
        )}
        {review && (
          <Check ok={g.positions_covered === g.positions_total}>
            {g.positions_covered} of {g.positions_total} playbook points reviewed
          </Check>
        )}
        {review && !review.playbook.validated_by && (
          <Check warn>Starter playbook, not yet approved by a lawyer at your firm</Check>
        )}
        {review?.playbook.validated_by && <Check ok>Playbook approved by {review.playbook.validated_by}</Check>}
        <Check ok>Only this matter&apos;s documents were available to the AI</Check>
        <Check ok>Text inside documents is treated as evidence, never as instructions</Check>
        <Check ok={run.status === "approved"} warn={run.status === "needs_review"}>
          {run.status === "approved" ? "Approved by a lawyer" : "Draft until a lawyer approves it"}
        </Check>
        <li className="faint" style={{ paddingTop: 8 }}>
          Cost {money(run.cost_usd)}{run.model ? ` · ${run.model}` : ""}
        </li>
      </ul>
    </div>
  );
}

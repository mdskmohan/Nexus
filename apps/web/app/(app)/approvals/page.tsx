"use client";

import { useEffect, useState } from "react";
import { Check, CheckCircle2, HelpCircle, Inbox, MessageSquareText, ShieldCheck, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Callout } from "@/components/ui/callout";
import { Card } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Field, Textarea } from "@/components/ui/form";
import { PageHeader } from "@/components/ui/page-header";
import { StatusPill } from "@/components/ui/status-pill";
import { api, type HumanRequest } from "@/lib/api";
import { when } from "@/lib/format";

export default function Approvals() {
  const [requests, setRequests] = useState<HumanRequest[] | null>(null);
  const [notes, setNotes] = useState<Record<string, string>>({});
  const [error, setError] = useState("");

  const load = () => api.get<HumanRequest[]>("/requests").then(setRequests);
  useEffect(() => { load(); }, []);

  async function decide(q: HumanRequest, decision: string) {
    setError("");
    try {
      const text = notes[q.id] ?? "";
      await api.post(`/requests/${q.id}/decide`, q.kind === "clarification"
        ? { decision: "answered", answer: text }
        : { decision, note: text });
      load();
    } catch (err) { setError((err as Error).message); }
  }

  return (
    <>
      <PageHeader title="Approvals" description="Runs pause here when they need a person to approve a step or answer a question." />
      {error && <Callout tone="danger">{error}</Callout>}
      {requests === null ? null : requests.length === 0 ? (
        <Card>
          <EmptyState icon={CheckCircle2} title="Nothing is waiting for you"
            description="When an agent needs an approval or an answer, it pauses and the request appears here." />
        </Card>
      ) : (
        <div className="space-y-4">
          {requests.map((q) => {
            const approval = q.kind === "approval";
            return (
              <Card key={q.id} className="overflow-hidden">
                <div className="flex items-start justify-between gap-4 px-5 py-4">
                  <div className="flex min-w-0 items-start gap-3">
                    <div className={approval ? "rounded-md bg-warning-soft p-2 text-warning-soft-foreground" : "rounded-md bg-info-soft p-2 text-info-soft-foreground"}>
                      {approval ? <ShieldCheck className="size-4" /> : <HelpCircle className="size-4" />}
                    </div>
                    <div className="min-w-0">
                      <p className="text-h2 text-foreground">{q.title}</p>
                      <p className="text-caption text-muted-foreground">
                        {q.run_title}{q.requested_for_name ? ` · started by ${q.requested_for_name}` : ""} · {when(q.created_at)}
                      </p>
                    </div>
                  </div>
                  <StatusPill tone={approval ? "warning" : "info"} pulse>{approval ? "Needs approval" : "Needs an answer"}</StatusPill>
                </div>
                {Object.keys(q.shown).length > 0 && (
                  <div className="border-y border-border bg-muted/40 px-5 py-3">
                    <p className="mb-1.5 flex items-center gap-1.5 text-caption font-medium uppercase tracking-wider text-muted-foreground">
                      <MessageSquareText className="size-3.5" /> What the agent shows you
                    </p>
                    <pre className="overflow-x-auto whitespace-pre-wrap font-mono text-caption text-foreground">{JSON.stringify(q.shown, null, 2)}</pre>
                  </div>
                )}
                <div className="space-y-3 px-5 py-4">
                  <Field label={approval ? "Note for the record" : "Your answer"} optional={approval}>
                    <Textarea rows={2} value={notes[q.id] ?? ""} onChange={(e) => setNotes({ ...notes, [q.id]: e.target.value })} />
                  </Field>
                  <div className="flex justify-end gap-2">
                    {approval ? (
                      <>
                        <Button variant="outline" onClick={() => decide(q, "rejected")}><X />Reject</Button>
                        <Button onClick={() => decide(q, "approved")}><Check />Approve</Button>
                      </>
                    ) : <Button onClick={() => decide(q, "answered")}><Check />Send answer</Button>}
                  </div>
                </div>
              </Card>
            );
          })}
        </div>
      )}
      <p className="flex items-center gap-1.5 text-caption text-muted-foreground"><Inbox className="size-3.5" /> Only requests your role may decide are shown.</p>
    </>
  );
}

"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import ModelPicker from "@/components/ModelPicker";

type Check = { ok: boolean; title: string; detail: string; source: string };
type Timeline = { cheque_valid_until: string; notice_last_day: string; checks: Check[]; amount_figures?: string; amount_words?: string };

const REASONS = ["Funds insufficient", "Exceeds arrangement", "Account closed", "Payment stopped by drawer",
  "Drawer's signature differs", "Refer to drawer"];
const ADVOCATE_KEY = "nexus.advocate";

const EMPTY = {
  payee_name: "", payee_address: "", drawer_name: "", drawer_address: "",
  cheque_number: "", cheque_date: "", amount: "", bank: "", presented_on: "", information_received_on: "",
  reason: REASONS[0], liability: "", advocate_name: "", advocate_address: "", enrolment_number: "",
  dispatch: "Registered Post with Acknowledgement Due and Speed Post",
};

function longDate(iso: string) {
  return new Date(iso + "T00:00:00").toLocaleDateString("en-IN", { day: "numeric", month: "long", year: "numeric" });
}

export function TimelineChecks({ checks }: { checks: Check[] }) {
  return (
    <ul style={{ listStyle: "none", margin: 0, padding: 0 }}>
      {checks.map((c, i) => (
        <li key={i} style={{ display: "grid", gridTemplateColumns: "20px 1fr", gap: 8, padding: "8px 0", borderBottom: "1px solid var(--line)" }}>
          <span style={{ color: c.ok ? "var(--ok)" : "var(--bad)", fontWeight: 700 }}>{c.ok ? "✓" : "!"}</span>
          <div>
            <div style={{ fontWeight: 600 }}>{c.title}</div>
            <div className="muted" style={{ fontSize: 14 }}>{c.detail}</div>
            <div className="faint">{c.source}</div>
          </div>
        </li>
      ))}
    </ul>
  );
}

export default function NoticeTab({ matterId }: { matterId: string }) {
  const router = useRouter();
  const [f, setF] = useState(EMPTY);
  const [modelId, setModelId] = useState("");
  const [timeline, setTimeline] = useState<Timeline | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const set = (k: keyof typeof EMPTY) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) =>
    setF((cur) => ({ ...cur, [k]: e.target.value }));

  // The advocate's details are remembered on this device, for convenience only.
  useEffect(() => {
    try {
      const saved = JSON.parse(localStorage.getItem(ADVOCATE_KEY) ?? "{}");
      setF((cur) => ({ ...cur, ...saved }));
    } catch {}
  }, []);

  const amount = Number(f.amount.replace(/[,\s]/g, ""));
  useEffect(() => {
    if (!f.cheque_date || !f.presented_on || !f.information_received_on) { setTimeline(null); return; }
    const t = setTimeout(() => {
      api.post<Timeline>("/notices/cheque/timeline", {
        cheque_date: f.cheque_date, presented_on: f.presented_on, information_received_on: f.information_received_on,
        amount: Number.isInteger(amount) && amount > 0 ? amount : null,
      }).then(setTimeline).catch(() => setTimeline(null));
    }, 250);
    return () => clearTimeout(t);
  }, [f.cheque_date, f.presented_on, f.information_received_on, amount]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      try {
        localStorage.setItem(ADVOCATE_KEY, JSON.stringify({ advocate_name: f.advocate_name, advocate_address: f.advocate_address, enrolment_number: f.enrolment_number }));
      } catch {}
      const { id } = await api.post<{ id: string }>(`/matters/${matterId}/notices/cheque`, { ...f, amount, model_id: modelId || null });
      router.push(`/tasks/${id}`);
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  }

  const late = timeline?.checks.some((c) => !c.ok);

  return (
    <div className="grid-2">
      <form className="card card-pad stack" onSubmit={submit}>
        <div>
          <h2>Cheque dishonour notice</h2>
          <p className="muted">Demand notice under section 138 of the Negotiable Instruments Act, 1881.</p>
        </div>

        <h3>Your client (payee)</h3>
        <label>Name<input required value={f.payee_name} onChange={set("payee_name")} /></label>
        <label>Address<textarea required rows={2} value={f.payee_address} onChange={set("payee_address")} /></label>

        <h3>The drawer</h3>
        <label>Name<input required value={f.drawer_name} onChange={set("drawer_name")} /></label>
        <label>Address for the notice<textarea required rows={2} value={f.drawer_address} onChange={set("drawer_address")} /></label>

        <h3>The cheque</h3>
        <div className="row">
          <label className="grow">Cheque number<input required value={f.cheque_number} onChange={set("cheque_number")} inputMode="numeric" /></label>
          <label className="grow">Date on the cheque<input required type="date" value={f.cheque_date} onChange={set("cheque_date")} /></label>
        </div>
        <label>Amount (₹)
          <input required value={f.amount} onChange={set("amount")} inputMode="numeric" placeholder="e.g. 450000" />
          {timeline?.amount_words && <span className="hint">₹ {timeline.amount_figures}/- · {timeline.amount_words}</span>}
        </label>
        <label>Drawn on (bank and branch)<input required value={f.bank} onChange={set("bank")} /></label>
        <label>What the cheque was for <span className="hint">The debt or liability it was given to discharge</span>
          <textarea required rows={3} value={f.liability} onChange={set("liability")} placeholder="e.g. payment for goods supplied under invoices dated 1 and 15 December 2025" />
        </label>

        <h3>Dishonour</h3>
        <div className="row">
          <label className="grow">Presented on<input required type="date" value={f.presented_on} onChange={set("presented_on")} /></label>
          <label className="grow">Client learned of the dishonour on <input required type="date" value={f.information_received_on} onChange={set("information_received_on")} /></label>
        </div>
        <label>Bank&apos;s reason (from the return memo)
          <select value={f.reason} onChange={set("reason")}>{REASONS.map((r) => <option key={r}>{r}</option>)}</select>
        </label>

        <h3>Advocate</h3>
        <div className="row">
          <label className="grow">Name<input required value={f.advocate_name} onChange={set("advocate_name")} placeholder="Adv. …" /></label>
          <label className="grow">Enrolment no. <span className="hint">Optional</span><input value={f.enrolment_number} onChange={set("enrolment_number")} /></label>
        </div>
        <label>Office address<textarea required rows={2} value={f.advocate_address} onChange={set("advocate_address")} /></label>
        <label>Sent by<input value={f.dispatch} onChange={set("dispatch")} /></label>

        <ModelPicker value={modelId} onChange={setModelId} />
        {error && <div className="notice notice-bad"><p>{error}</p></div>}
        <div className="row"><button className="btn-primary" disabled={busy}>{busy ? "Starting…" : "Draft the notice"}</button></div>
      </form>

      <div className="stack">
        <div className="card">
          <div className="card-head"><h3>Statutory timeline</h3></div>
          <div className="card-pad" style={{ paddingTop: 8 }}>
            {timeline ? (
              <>
                <p style={{ marginBottom: 8 }}>
                  Send the notice by <strong>{longDate(timeline.notice_last_day)}</strong>.
                </p>
                <TimelineChecks checks={timeline.checks} />
                {late && <div className="notice notice-bad" style={{ marginTop: 12 }}><p>A statutory requirement is not met. Check the dates before sending this notice.</p></div>}
              </>
            ) : <p className="muted">Enter the cheque date, presentation date and the date your client learned of the dishonour. Nexus works out the deadlines under sections 138 and 142.</p>}
          </div>
        </div>
        <div className="card card-pad stack" style={{ gap: 8 }}>
          <h3>How this notice is checked</h3>
          <p className="muted">Dates and amounts are calculated by Nexus, not by the AI.</p>
          <p className="muted">Before you see the draft, Nexus checks that the cheque number, amount in figures and words, cheque date, bank, names, reason and the 15-day demand all match what you entered.</p>
        </div>
      </div>
    </div>
  );
}

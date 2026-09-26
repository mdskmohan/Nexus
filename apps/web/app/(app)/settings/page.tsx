"use client";

import { useEffect, useRef, useState } from "react";
import { api, atLeast, type Role, ROLE_ORDER } from "@/lib/api";
import { when } from "@/lib/format";
import { useMe } from "@/lib/me";

type Member = { id: string; name: string; email: string; role: Role; disabled: boolean; created_at: string };

const ROLE_HELP: Record<Role, string> = {
  paralegal: "Can work on matters and run AI tasks.",
  associate: "Can also approve AI work and remove documents.",
  partner: "Can also edit and approve playbooks, change firm preferences and see the audit trail.",
  admin: "Can also manage the team.",
};

export default function Settings() {
  const me = useMe();
  const [prefs, setPrefs] = useState(me.firm.preferences);
  const [saved, setSaved] = useState(false);
  const [team, setTeam] = useState<Member[]>([]);
  const [member, setMember] = useState({ name: "", email: "", role: "associate" as Role, temporary_password: "" });
  const [error, setError] = useState("");
  const dialog = useRef<HTMLDialogElement>(null);
  const isAdmin = me.user.role === "admin";
  const canEditPrefs = atLeast(me.user.role, "partner");

  const loadTeam = () => api.get<Member[]>("/team").then(setTeam);
  useEffect(() => { loadTeam(); }, []);

  async function savePrefs() {
    await api.patch("/firm", { preferences: prefs });
    setSaved(true);
    setTimeout(() => setSaved(false), 2500);
  }

  async function addMember(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    try {
      await api.post("/team", member);
      dialog.current?.close();
      setMember({ name: "", email: "", role: "associate", temporary_password: "" });
      loadTeam();
    } catch (err) { setError((err as Error).message); }
  }

  async function update(id: string, change: Partial<Member>) {
    await api.patch(`/team/${id}`, change);
    loadTeam();
  }

  return (
    <div className="stack" style={{ gap: 28 }}>
      <div className="page-head" style={{ marginBottom: 0 }}>
        <div><h1>Firm settings</h1><p>{me.firm.name}</p></div>
      </div>

      <section className="card card-pad stack">
        <div>
          <h2>How your firm likes things done</h2>
          <p className="muted">The AI reads this before every task. Write it the way you would brief a new associate.</p>
        </div>
        <textarea rows={7} disabled={!canEditPrefs} value={prefs} onChange={(e) => setPrefs(e.target.value)}
          placeholder={"e.g.\n- Use British English and the defined terms used in the document.\n- We act mostly for Indian technology companies contracting with US customers.\n- Flag any clause that gives the other side a unilateral right to change terms."} />
        {canEditPrefs && (
          <div className="row">
            <button className="btn-primary" onClick={savePrefs}>Save</button>
            {saved && <span className="pill pill-ok">Saved</span>}
          </div>
        )}
      </section>

      <section className="stack">
        <div className="row" style={{ justifyContent: "space-between" }}>
          <div><h2>Team</h2><p className="muted">Everyone at the firm can see the firm&apos;s matters.</p></div>
          {isAdmin && <button className="btn-primary" onClick={() => dialog.current?.showModal()}>Add a colleague</button>}
        </div>
        <div className="card">
          <table>
            <thead><tr><th>Name</th><th>Role</th><th>Joined</th><th></th></tr></thead>
            <tbody>
              {team.map((m) => (
                <tr key={m.id} style={{ opacity: m.disabled ? 0.55 : 1 }}>
                  <td><div style={{ fontWeight: 600 }}>{m.name}{m.disabled ? " (access removed)" : ""}</div><div className="faint">{m.email}</div></td>
                  <td>
                    {isAdmin && m.id !== me.user.id ? (
                      <select value={m.role} onChange={(e) => update(m.id, { role: e.target.value as Role })} style={{ width: 150 }}>
                        {ROLE_ORDER.map((r) => <option key={r} value={r}>{r}</option>)}
                      </select>
                    ) : <span style={{ textTransform: "capitalize" }}>{m.role}</span>}
                  </td>
                  <td className="muted">{when(m.created_at)}</td>
                  <td style={{ textAlign: "right" }}>
                    {isAdmin && m.id !== me.user.id && (
                      <button className="btn-quiet btn-small" onClick={() => update(m.id, { disabled: !m.disabled })}>
                        {m.disabled ? "Restore access" : "Remove access"}
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="card card-pad stack" style={{ gap: 4 }}>
          {ROLE_ORDER.map((r) => <p key={r} className="muted"><strong style={{ textTransform: "capitalize", color: "var(--ink)" }}>{r}.</strong> {ROLE_HELP[r]}</p>)}
        </div>
      </section>

      <dialog ref={dialog}>
        <form className="card-pad stack" onSubmit={addMember}>
          <h2>Add a colleague</h2>
          <label>Name<input required value={member.name} onChange={(e) => setMember({ ...member, name: e.target.value })} /></label>
          <label>Email<input type="email" required value={member.email} onChange={(e) => setMember({ ...member, email: e.target.value })} /></label>
          <label>Role
            <select value={member.role} onChange={(e) => setMember({ ...member, role: e.target.value as Role })}>
              {ROLE_ORDER.map((r) => <option key={r} value={r}>{r}</option>)}
            </select>
            <span className="hint">{ROLE_HELP[member.role]}</span>
          </label>
          <label>Temporary password <span className="hint">At least 10 characters. Share it with them privately.</span>
            <input required minLength={10} value={member.temporary_password} onChange={(e) => setMember({ ...member, temporary_password: e.target.value })} />
          </label>
          {error && <div className="notice notice-bad"><p>{error}</p></div>}
          <div className="row" style={{ justifyContent: "flex-end" }}>
            <button type="button" className="btn-quiet" onClick={() => dialog.current?.close()}>Cancel</button>
            <button className="btn-primary">Add</button>
          </div>
        </form>
      </dialog>
    </div>
  );
}

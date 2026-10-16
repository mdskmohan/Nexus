"use client";

import { useEffect, useRef, useState } from "react";
import { api, can, type Role, ROLES } from "@/lib/api";
import { when } from "@/lib/format";
import { useMe } from "@/lib/me";
import AiModels from "@/components/settings/AiModels";

type Member = { id: string; name: string; email: string; role: Role; disabled: boolean; created_at: string };

const ROLE_HELP: Record<Role, string> = {
  admin: "Everything, including people, AI models and connections.",
  steward: "Approves knowledge-graph changes and runs; sees the audit trail.",
  developer: "Builds, tests and publishes agents; approves runs.",
  analyst: "Runs agents and answers their questions.",
  viewer: "Uses published apps.",
};

export default function Settings() {
  const me = useMe();
  const [team, setTeam] = useState<Member[]>([]);
  const [member, setMember] = useState({ name: "", email: "", role: "analyst" as Role, temporary_password: "" });
  const [error, setError] = useState("");
  const dialog = useRef<HTMLDialogElement>(null);
  const isAdmin = can(me, "manage_people");

  const loadTeam = () => api.get<Member[]>("/team").then(setTeam);
  useEffect(() => { loadTeam(); }, []);

  async function addMember(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    try {
      await api.post("/team", member);
      dialog.current?.close();
      setMember({ name: "", email: "", role: "analyst", temporary_password: "" });
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
        <div><h1>Workspace settings</h1><p>{me.workspace.name}</p></div>
      </div>

      {can(me, "manage_ai") && <AiModels />}

      <section className="stack">
        <div className="row" style={{ justifyContent: "space-between" }}>
          <div><h2>Team</h2><p className="muted">Each person&apos;s role decides what they can build, run and approve.</p></div>
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
                        {ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
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
          {ROLES.map((r) => <p key={r} className="muted"><strong style={{ textTransform: "capitalize", color: "var(--ink)" }}>{r}.</strong> {ROLE_HELP[r]}</p>)}
        </div>
      </section>

      <dialog ref={dialog}>
        <form className="card-pad stack" onSubmit={addMember}>
          <h2>Add a colleague</h2>
          <label>Name<input required value={member.name} onChange={(e) => setMember({ ...member, name: e.target.value })} /></label>
          <label>Email<input type="email" required value={member.email} onChange={(e) => setMember({ ...member, email: e.target.value })} /></label>
          <label>Role
            <select value={member.role} onChange={(e) => setMember({ ...member, role: e.target.value as Role })}>
              {ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
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

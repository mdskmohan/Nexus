"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api, type Playbook } from "@/lib/api";

export default function Playbooks() {
  const router = useRouter();
  const [playbooks, setPlaybooks] = useState<Playbook[] | null>(null);
  useEffect(() => { api.get<Playbook[]>("/playbooks").then(setPlaybooks); }, []);

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Review playbooks</h1>
          <p>Your firm&apos;s checklists for reviewing contracts: what you want, what you can accept, and what must always be raised.</p>
        </div>
      </div>
      <div className="notice notice-info" style={{ marginBottom: 20 }}>
        <p>Nexus starts you with general-practice playbooks. They are a starting point, not legal advice for any jurisdiction. A partner should read, adjust and approve each one before the firm relies on it.</p>
      </div>
      <div className="card">
        {playbooks === null ? <div className="empty">Loading…</div> : (
          <table>
            <thead><tr><th>Playbook</th><th>Points</th><th>Status</th></tr></thead>
            <tbody>
              {playbooks.map((p) => (
                <tr key={p.id} className="link-row" onClick={() => router.push(`/playbooks/${p.id}`)}>
                  <td><div style={{ fontWeight: 600 }}>{p.name}</div><div className="faint">{p.description}</div></td>
                  <td>{p.position_count}</td>
                  <td>
                    {p.validated_by
                      ? <span className="pill pill-ok">Approved by {p.validated_by}</span>
                      : <span className="pill pill-warn">Not yet approved</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </>
  );
}

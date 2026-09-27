"use client";

import { useRouter } from "next/navigation";
import type { Run } from "@/lib/api";
import { RUN_STATUS, when } from "@/lib/format";

export default function HistoryTab({ runs }: { runs: Run[] }) {
  const router = useRouter();
  if (!runs.length) return <div className="card empty">No questions or reviews yet.</div>;
  return (
    <div className="card">
      <table>
        <thead><tr><th>Task</th><th>Status</th><th>Started</th></tr></thead>
        <tbody>
          {runs.map((r) => (
            <tr key={r.id} className="link-row" onClick={() => router.push(`/tasks/${r.id}`)}>
              <td>
                <div className="faint">{{ ask: "Question", review: "Contract review", draft: "Drafting", notice: "Legal notice" }[r.kind]}</div>
                <div style={{ fontWeight: 600 }}>{r.title}</div>
              </td>
              <td>
                <span className={RUN_STATUS[r.status].tone}>{RUN_STATUS[r.status].label}</span>
                {r.reviewed_by_name && <div className="faint" style={{ marginTop: 4 }}>by {r.reviewed_by_name}</div>}
              </td>
              <td className="muted">{when(r.created_at)}{r.created_by_name ? ` by ${r.created_by_name}` : ""}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

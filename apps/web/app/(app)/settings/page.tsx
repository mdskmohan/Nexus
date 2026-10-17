"use client";

import { useEffect, useRef, useState } from "react";
import { Bot, History, ShieldCheck, UserPlus, Users } from "lucide-react";
import AiModels from "@/components/settings/AiModels";
import { Avatar } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Callout } from "@/components/ui/callout";
import { Card } from "@/components/ui/card";
import { Dialog } from "@/components/ui/dialog";
import { Field, Input, Select } from "@/components/ui/form";
import { PageHeader } from "@/components/ui/page-header";
import { StatusPill } from "@/components/ui/status-pill";
import { Table, Td, Th, Tr } from "@/components/ui/table";
import { Tabs } from "@/components/ui/tabs";
import { api, can, type Role, ROLES } from "@/lib/api";
import { when } from "@/lib/format";
import { useMe } from "@/lib/me";

type Member = { id: string; name: string; email: string; role: Role; disabled: boolean; created_at: string };
type AuditEvent = { id: number; action: string; target_type: string; target_id: string | null; at: string; actor_name: string | null };
type Tab = "team" | "ai" | "audit";

const ROLE_HELP: Record<Role, string> = {
  admin: "Everything, including people, AI models and connections.",
  steward: "Approves knowledge-graph changes and runs; sees the audit trail.",
  developer: "Builds, tests and publishes agents; approves runs.",
  analyst: "Runs agents and answers their questions.",
  viewer: "Uses published apps.",
};

export default function Settings() {
  const me = useMe();
  const isAdmin = can(me, "manage_people");
  const tabs = [
    { id: "team" as Tab, label: "Team", icon: <Users /> },
    ...(can(me, "manage_ai") ? [{ id: "ai" as Tab, label: "AI models", icon: <Bot /> }] : []),
    ...(can(me, "view_audit") ? [{ id: "audit" as Tab, label: "Audit trail", icon: <History /> }] : []),
  ];
  const [tab, setTab] = useState<Tab>("team");
  const [team, setTeam] = useState<Member[]>([]);
  const [audit, setAudit] = useState<AuditEvent[] | null>(null);
  const [member, setMember] = useState({ name: "", email: "", role: "analyst" as Role, temporary_password: "" });
  const [error, setError] = useState("");
  const dialog = useRef<HTMLDialogElement>(null);

  const loadTeam = () => api.get<Member[]>("/team").then(setTeam);
  useEffect(() => { loadTeam(); }, []);
  useEffect(() => { if (tab === "audit" && audit === null) api.get<AuditEvent[]>("/audit").then(setAudit); }, [tab, audit]);

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
    <>
      <PageHeader title="Settings" description={me.workspace.name}
        actions={tab === "team" && isAdmin && <Button onClick={() => dialog.current?.showModal()}><UserPlus />Add a colleague</Button>} />
      <Tabs tabs={tabs} value={tab} onChange={setTab} />

      {tab === "team" && (
        <div className="space-y-4">
          <Card>
            <Table>
              <thead><tr><Th>Person</Th><Th>Role</Th><Th>Joined</Th><Th /></tr></thead>
              <tbody>
                {team.map((m) => (
                  <Tr key={m.id} className={m.disabled ? "opacity-55" : ""}>
                    <Td>
                      <div className="flex items-center gap-3">
                        <Avatar name={m.name} />
                        <div>
                          <div className="font-medium text-foreground">{m.name}{m.disabled && <span className="ml-2 text-caption text-muted-foreground">access removed</span>}</div>
                          <div className="text-caption text-muted-foreground">{m.email}</div>
                        </div>
                      </div>
                    </Td>
                    <Td>
                      {isAdmin && m.id !== me.user.id ? (
                        <Select className="h-8 w-36 capitalize" value={m.role} onChange={(e) => update(m.id, { role: e.target.value as Role })}>
                          {ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
                        </Select>
                      ) : <StatusPill tone="primary" className="capitalize">{m.role}</StatusPill>}
                    </Td>
                    <Td className="text-muted-foreground">{when(m.created_at)}</Td>
                    <Td className="text-right">
                      {isAdmin && m.id !== me.user.id && (
                        <Button variant="ghost" size="sm" onClick={() => update(m.id, { disabled: !m.disabled })}>
                          {m.disabled ? "Restore access" : "Remove access"}
                        </Button>
                      )}
                    </Td>
                  </Tr>
                ))}
              </tbody>
            </Table>
          </Card>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {ROLES.map((r) => (
              <div key={r} className="rounded-lg border border-border bg-card p-4">
                <div className="flex items-center gap-2">
                  <ShieldCheck className="size-4 text-primary" />
                  <span className="font-medium capitalize text-foreground">{r}</span>
                </div>
                <p className="mt-1 text-caption text-muted-foreground">{ROLE_HELP[r]}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {tab === "ai" && <AiModels />}

      {tab === "audit" && (
        <Card>
          <Table>
            <thead><tr><Th>What happened</Th><Th>Who</Th><Th>When</Th></tr></thead>
            <tbody>
              {(audit ?? []).map((a) => (
                <Tr key={a.id}>
                  <Td><span className="font-mono text-caption text-foreground">{a.action}</span> <span className="text-caption text-muted-foreground">{a.target_type}</span></Td>
                  <Td className="text-muted-foreground">{a.actor_name ?? "Nexus"}</Td>
                  <Td className="text-muted-foreground">{when(a.at)}</Td>
                </Tr>
              ))}
            </tbody>
          </Table>
        </Card>
      )}

      <Dialog ref={dialog} title="Add a colleague" description="They sign in with a temporary password you share privately.">
        <form className="space-y-4" onSubmit={addMember}>
          <Field label="Name"><Input required value={member.name} onChange={(e) => setMember({ ...member, name: e.target.value })} /></Field>
          <Field label="Email"><Input type="email" required value={member.email} onChange={(e) => setMember({ ...member, email: e.target.value })} /></Field>
          <Field label="Role" hint={ROLE_HELP[member.role]}>
            <Select className="capitalize" value={member.role} onChange={(e) => setMember({ ...member, role: e.target.value as Role })}>
              {ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
            </Select>
          </Field>
          <Field label="Temporary password" hint="At least 10 characters.">
            <Input required minLength={10} value={member.temporary_password} onChange={(e) => setMember({ ...member, temporary_password: e.target.value })} />
          </Field>
          {error && <Callout tone="danger">{error}</Callout>}
          <div className="flex justify-end gap-2 pt-1">
            <Button type="button" variant="ghost" onClick={() => dialog.current?.close()}>Cancel</Button>
            <Button>Add</Button>
          </div>
        </form>
      </Dialog>
    </>
  );
}

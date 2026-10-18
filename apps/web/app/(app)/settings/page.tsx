"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useRef, useState } from "react";
import {
  Bot, Building2, Check, Copy, History, KeyRound, Loader2, Lock, Pencil, Settings as SettingsIcon, ShieldCheck,
  UserPlus, UserRound, Users, X,
} from "lucide-react";
import AiModels from "@/components/settings/AiModels";
import { Avatar } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Callout } from "@/components/ui/callout";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { Dialog } from "@/components/ui/dialog";
import { Field, Input, Select } from "@/components/ui/form";
import { PageHeader } from "@/components/ui/page-header";
import { StatusPill } from "@/components/ui/status-pill";
import { Table, Td, Th, Tr } from "@/components/ui/table";
import { Tabs } from "@/components/ui/tabs";
import { useToast } from "@/components/ui/toast";
import { api, can, type Role, ROLES } from "@/lib/api";
import { when } from "@/lib/format";
import { useMe, useRefreshMe } from "@/lib/me";

type Member = { id: string; name: string; email: string; role: Role; disabled: boolean; created_at: string };
type AuditEvent = { id: number; action: string; target_type: string; target_id: string | null; at: string; actor_name: string | null };
type Tab = "general" | "team" | "ai" | "audit";

const MIN_PASSWORD = 10;

const ROLE_HELP: Record<Role, string> = {
  admin: "Everything, including people, AI models and connections.",
  steward: "Approves knowledge-graph changes and runs; sees the audit trail.",
  developer: "Builds, tests and publishes agents; approves runs.",
  analyst: "Runs agents and answers their questions.",
  viewer: "Uses published apps.",
};

export default function SettingsPage() {
  return <Suspense><Settings /></Suspense>;
}

function Settings() {
  const me = useMe();
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const tabs = [
    { id: "general" as Tab, label: "General", icon: <SettingsIcon /> },
    { id: "team" as Tab, label: "Team", icon: <Users /> },
    ...(can(me, "manage_ai") ? [{ id: "ai" as Tab, label: "AI models", icon: <Bot /> }] : []),
    ...(can(me, "view_audit") ? [{ id: "audit" as Tab, label: "Audit trail", icon: <History /> }] : []),
  ];
  const asked = params.get("tab") as Tab | null;
  const tab: Tab = tabs.some((t) => t.id === asked) ? asked! : "general";

  function choose(next: Tab) {
    const q = new URLSearchParams(params.toString());
    if (next === "general") q.delete("tab"); else q.set("tab", next);
    router.replace(`${pathname}${q.size ? `?${q}` : ""}`, { scroll: false });
  }

  return (
    <div className="max-w-4xl space-y-6">
      <PageHeader title="Settings" description="Your workspace, your profile, the team, AI models and the audit trail." />
      <Tabs tabs={tabs} value={tab} onChange={choose} />
      {tab === "general" && <General />}
      {tab === "team" && <Team />}
      {tab === "ai" && <AiModels />}
      {tab === "audit" && <Audit />}
    </div>
  );
}

// General ------------------------------------------------------------------------------------

function General() {
  const me = useMe();
  const refreshMe = useRefreshMe();
  const toast = useToast();
  const [copied, setCopied] = useState(false);

  async function save(path: string, body: object, done: string) {
    await api.patch(path, body);
    await refreshMe();
    toast({ tone: "success", title: done });
  }

  return (
    <div className="space-y-5">
      <Card>
        <CardHeader icon={<Building2 />} title="Workspace" description="Everyone in the workspace sees its name." />
        <CardBody className="space-y-5">
          <EditableField label="Workspace name" value={me.workspace.name} minLength={2} disabled={!can(me, "manage_workspace")}
            disabledHint="Only an administrator can rename the workspace."
            onSave={(name) => save("/workspace", { name }, "Workspace renamed")} />
          <div className="space-y-1.5">
            <p className="text-caption text-muted-foreground">Workspace ID</p>
            <div className="flex items-center gap-2">
              <code className="rounded-md bg-muted px-2 py-1 font-mono text-caption text-foreground">{me.workspace.id}</code>
              <button aria-label="Copy the workspace ID" onClick={() => navigator.clipboard.writeText(me.workspace.id).then(() => { setCopied(true); setTimeout(() => setCopied(false), 1500); })}
                className="inline-flex size-7 items-center justify-center rounded-md text-muted-foreground hover:bg-accent hover:text-foreground">
                {copied ? <Check className="size-3.5 text-success" /> : <Copy className="size-3.5" />}
              </button>
            </div>
          </div>
        </CardBody>
      </Card>

      <Card>
        <CardHeader icon={<UserRound />} title="Profile" description="How you appear to colleagues, in approvals and in the audit trail." />
        <CardBody className="space-y-5">
          <div className="flex items-center gap-4">
            <Avatar name={me.user.name} className="size-12 text-body" />
            <div className="min-w-0">
              <p className="truncate text-h2 text-foreground">{me.user.name}</p>
              <p className="truncate text-body text-muted-foreground">{me.user.email}</p>
            </div>
            <StatusPill tone="primary" className="ml-auto capitalize">{me.user.role}</StatusPill>
          </div>
          <EditableField label="Name" value={me.user.name} minLength={1} onSave={(name) => save("/me", { name }, "Profile updated")} />
          <div className="space-y-1.5">
            <p className="text-caption text-muted-foreground">Email</p>
            <p className="text-body text-foreground">{me.user.email}</p>
            <p className="text-caption text-muted-foreground">Your email is how you sign in. Ask an administrator to change it.</p>
          </div>
          <div className="space-y-1.5">
            <p className="text-caption text-muted-foreground">Role</p>
            <p className="text-body text-foreground"><span className="capitalize">{me.user.role}</span> · {ROLE_HELP[me.user.role]}</p>
          </div>
        </CardBody>
      </Card>

      <PasswordCard />
    </div>
  );
}

function EditableField({ label, value, onSave, minLength, disabled, disabledHint }: {
  label: string; value: string; onSave: (v: string) => Promise<void>; minLength: number; disabled?: boolean; disabledHint?: string;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(value);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    const next = draft.trim();
    if (next === value) { setEditing(false); return; }
    setSaving(true); setError("");
    try { await onSave(next); setEditing(false); }
    catch (err) { setError((err as Error).message); }
    finally { setSaving(false); }
  }

  if (editing) {
    return (
      <form onSubmit={submit} className="space-y-1.5">
        <label className="text-caption text-muted-foreground" htmlFor={label}>{label}</label>
        <div className="flex items-center gap-2">
          <Input id={label} autoFocus required minLength={minLength} maxLength={200} value={draft} className="max-w-sm"
            onChange={(e) => setDraft(e.target.value)} onKeyDown={(e) => { if (e.key === "Escape") setEditing(false); }} />
          <Button size="icon" aria-label="Save" disabled={saving}>{saving ? <Loader2 className="animate-spin" /> : <Check />}</Button>
          <Button type="button" size="icon" variant="ghost" aria-label="Cancel" onClick={() => setEditing(false)}><X /></Button>
        </div>
        {error && <p className="text-caption text-danger">{error}</p>}
      </form>
    );
  }
  return (
    <div className="space-y-1.5">
      <p className="text-caption text-muted-foreground">{label}</p>
      <div className="flex items-center gap-2">
        <p className="text-body font-medium text-foreground">{value}</p>
        {!disabled && (
          <button aria-label={`Edit ${label.toLowerCase()}`} onClick={() => { setDraft(value); setError(""); setEditing(true); }}
            className="inline-flex size-7 items-center justify-center rounded-md text-muted-foreground hover:bg-accent hover:text-foreground">
            <Pencil className="size-3.5" />
          </button>
        )}
      </div>
      {disabled && disabledHint && <p className="text-caption text-muted-foreground">{disabledHint}</p>}
    </div>
  );
}

function PasswordCard() {
  const toast = useToast();
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ current: "", next: "", confirm: "" });
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const mismatch = form.confirm.length > 0 && form.next !== form.confirm;

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (form.next !== form.confirm) { setError("The new passwords do not match."); return; }
    setSaving(true); setError("");
    try {
      await api.patch("/me", { current_password: form.current, new_password: form.next });
      setForm({ current: "", next: "", confirm: "" }); setOpen(false);
      toast({ tone: "success", title: "Password changed", description: "Use the new password next time you sign in." });
    } catch (err) { setError((err as Error).message); }
    finally { setSaving(false); }
  }

  return (
    <Card>
      <CardHeader icon={<Lock />} title="Password" description="At least 10 characters. You need your current password to change it."
        actions={!open && <Button variant="outline" size="sm" onClick={() => setOpen(true)}><KeyRound />Change password</Button>} />
      {open && (
        <CardBody>
          <form onSubmit={submit} className="max-w-sm space-y-4">
            <Field label="Current password">
              <Input type="password" required autoComplete="current-password" value={form.current} onChange={(e) => setForm({ ...form, current: e.target.value })} />
            </Field>
            <Field label="New password" hint={`At least ${MIN_PASSWORD} characters.`}>
              <Input type="password" required minLength={MIN_PASSWORD} autoComplete="new-password" value={form.next} onChange={(e) => setForm({ ...form, next: e.target.value })} />
            </Field>
            <Field label="Confirm the new password">
              <Input type="password" required autoComplete="new-password" aria-invalid={mismatch} value={form.confirm} onChange={(e) => setForm({ ...form, confirm: e.target.value })} />
            </Field>
            {mismatch && <p className="-mt-2 text-caption text-danger">The new passwords do not match.</p>}
            {error && <Callout tone="danger">{error}</Callout>}
            <div className="flex gap-2">
              <Button disabled={saving || mismatch}>{saving && <Loader2 className="animate-spin" />}Change password</Button>
              <Button type="button" variant="ghost" onClick={() => { setOpen(false); setError(""); setForm({ current: "", next: "", confirm: "" }); }}>Cancel</Button>
            </div>
          </form>
        </CardBody>
      )}
    </Card>
  );
}

// Team ---------------------------------------------------------------------------------------

function Team() {
  const me = useMe();
  const toast = useToast();
  const isAdmin = can(me, "manage_people");
  const [team, setTeam] = useState<Member[] | null>(null);
  const [member, setMember] = useState({ name: "", email: "", role: "analyst" as Role, temporary_password: "" });
  const [error, setError] = useState("");
  const dialog = useRef<HTMLDialogElement>(null);

  const load = () => api.get<Member[]>("/team").then(setTeam);
  useEffect(() => { load(); }, []);

  async function addMember(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    try {
      await api.post("/team", member);
      dialog.current?.close();
      toast({ tone: "success", title: `${member.name} added`, description: "Share their temporary password with them privately." });
      setMember({ name: "", email: "", role: "analyst", temporary_password: "" });
      load();
    } catch (err) { setError((err as Error).message); }
  }

  async function update(m: Member, change: Partial<Member>) {
    try { await api.patch(`/team/${m.id}`, change); load(); }
    catch (err) { toast({ tone: "danger", title: "Could not update", description: (err as Error).message }); }
  }

  const active = team?.filter((m) => !m.disabled).length ?? 0;

  return (
    <div className="space-y-5">
      <Card>
        <CardHeader icon={<Users />} title="People" description={team ? `${active} with access${team.length > active ? `, ${team.length - active} removed` : ""}` : "Loading…"}
          actions={isAdmin && <Button size="sm" onClick={() => dialog.current?.showModal()}><UserPlus />Add a colleague</Button>} />
        <Table>
          <thead><tr><Th>Person</Th><Th>Role</Th><Th>Joined</Th><Th /></tr></thead>
          <tbody>
            {(team ?? []).map((m) => (
              <Tr key={m.id} className={m.disabled ? "opacity-55" : ""}>
                <Td>
                  <div className="flex items-center gap-3">
                    <Avatar name={m.name} />
                    <div className="min-w-0">
                      <div className="truncate font-medium text-foreground">
                        {m.name}{m.id === me.user.id && <span className="ml-2 text-caption text-muted-foreground">you</span>}
                        {m.disabled && <span className="ml-2 text-caption text-muted-foreground">access removed</span>}
                      </div>
                      <div className="truncate text-caption text-muted-foreground">{m.email}</div>
                    </div>
                  </div>
                </Td>
                <Td>
                  {isAdmin && m.id !== me.user.id ? (
                    <Select aria-label={`Role of ${m.name}`} className="h-8 w-36 capitalize" value={m.role} onChange={(e) => update(m, { role: e.target.value as Role })}>
                      {ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
                    </Select>
                  ) : <StatusPill tone="primary" className="capitalize">{m.role}</StatusPill>}
                </Td>
                <Td className="text-muted-foreground">{when(m.created_at)}</Td>
                <Td className="text-right">
                  {isAdmin && m.id !== me.user.id && (
                    <Button variant="ghost" size="sm" className={m.disabled ? "" : "hover:text-danger"} onClick={() => update(m, { disabled: !m.disabled })}>
                      {m.disabled ? "Restore access" : "Remove access"}
                    </Button>
                  )}
                </Td>
              </Tr>
            ))}
          </tbody>
        </Table>
      </Card>

      <Card>
        <CardHeader icon={<ShieldCheck />} title="Roles" description="What each role can do in this workspace." />
        <div className="grid gap-px overflow-hidden rounded-b-lg bg-border sm:grid-cols-2 lg:grid-cols-3">
          {ROLES.map((r) => (
            <div key={r} className="bg-card p-4">
              <p className="font-medium capitalize text-foreground">{r}</p>
              <p className="mt-1 text-caption text-muted-foreground">{ROLE_HELP[r]}</p>
            </div>
          ))}
        </div>
      </Card>

      <Dialog ref={dialog} title="Add a colleague" description="They sign in with a temporary password you share privately.">
        <form className="space-y-4" onSubmit={addMember}>
          <Field label="Name"><Input required value={member.name} onChange={(e) => setMember({ ...member, name: e.target.value })} /></Field>
          <Field label="Email"><Input type="email" required value={member.email} onChange={(e) => setMember({ ...member, email: e.target.value })} /></Field>
          <Field label="Role" hint={ROLE_HELP[member.role]}>
            <Select className="capitalize" value={member.role} onChange={(e) => setMember({ ...member, role: e.target.value as Role })}>
              {ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
            </Select>
          </Field>
          <Field label="Temporary password" hint={`At least ${MIN_PASSWORD} characters.`}>
            <Input required minLength={MIN_PASSWORD} autoComplete="new-password" value={member.temporary_password} onChange={(e) => setMember({ ...member, temporary_password: e.target.value })} />
          </Field>
          {error && <Callout tone="danger">{error}</Callout>}
          <div className="flex justify-end gap-2 pt-1">
            <Button type="button" variant="ghost" onClick={() => dialog.current?.close()}>Cancel</Button>
            <Button>Add</Button>
          </div>
        </form>
      </Dialog>
    </div>
  );
}

// Audit trail --------------------------------------------------------------------------------

function Audit() {
  const [events, setEvents] = useState<AuditEvent[] | null>(null);
  const [q, setQ] = useState("");
  useEffect(() => { api.get<AuditEvent[]>("/audit").then(setEvents); }, []);
  const term = q.trim().toLowerCase();
  const shown = (events ?? []).filter((a) => !term || `${a.action} ${a.target_type} ${a.actor_name ?? ""}`.toLowerCase().includes(term));

  return (
    <Card>
      <CardHeader icon={<History />} title="Audit trail" description="Every change in the workspace, newest first. Entries cannot be edited or deleted."
        actions={<Input aria-label="Filter the audit trail" placeholder="Filter" value={q} onChange={(e) => setQ(e.target.value)} className="h-8 w-44" />} />
      {events === null ? (
        <p className="flex items-center gap-2 px-5 py-8 text-body text-muted-foreground"><Loader2 className="size-4 animate-spin" />Loading…</p>
      ) : (
        <Table>
          <thead><tr><Th>What happened</Th><Th>Who</Th><Th>When</Th></tr></thead>
          <tbody>
            {shown.map((a) => (
              <Tr key={a.id}>
                <Td><span className="font-mono text-caption text-foreground">{a.action}</span> <span className="text-caption text-muted-foreground">{a.target_type}</span></Td>
                <Td className="text-muted-foreground">{a.actor_name ?? "Nexus"}</Td>
                <Td className="text-muted-foreground" title={new Date(a.at).toLocaleString()}>{when(a.at)}</Td>
              </Tr>
            ))}
            {shown.length === 0 && <tr><td colSpan={3} className="px-5 py-8 text-center text-body text-muted-foreground">Nothing matches.</td></tr>}
          </tbody>
        </Table>
      )}
    </Card>
  );
}

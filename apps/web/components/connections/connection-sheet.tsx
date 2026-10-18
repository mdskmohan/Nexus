"use client";

import { useEffect, useRef, useState } from "react";
import { ChevronRight, ExternalLink, Loader2, Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Callout } from "@/components/ui/callout";
import { Field, Input, Select, Textarea } from "@/components/ui/form";
import { Sheet } from "@/components/ui/sheet";
import { api, type Connection, type ConnectorSpec } from "@/lib/api";
import { KindMark, VerifiedBadge } from "./kinds";

/**
 * Adding a connection (choose the platform, then fill in its settings) or editing one (its settings only).
 * Secrets are never sent back to the browser: when editing, a blank secret keeps the saved one.
 */
export function ConnectionSheet({ open, specs, editing, onClose, onSaved }: {
  open: boolean; specs: ConnectorSpec[]; editing?: Connection | null;
  onClose: () => void; onSaved: (id: string) => void;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  const [kind, setKind] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [label, setLabel] = useState("");
  const [values, setValues] = useState<Record<string, string>>({});
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (open && !dialog.open) {
      setError(""); setSearch(""); setSaving(false);
      setKind(editing?.kind ?? null);
      setLabel(editing?.label ?? "");
      setValues(editing ? { ...editing.config } : {});
      dialog.showModal();
    } else if (!open && dialog.open) dialog.close();
  }, [open, editing]);

  useEffect(() => {
    const dialog = ref.current;
    const closed = () => onClose();
    dialog?.addEventListener("close", closed);
    return () => dialog?.removeEventListener("close", closed);
  }, [onClose]);

  const spec = specs.find((s) => s.kind === kind);
  const q = search.trim().toLowerCase();
  const shown = specs.filter((s) => !q || `${s.name} ${s.description}`.toLowerCase().includes(q));
  const verified = specs.filter((s) => s.verified).length;

  function choose(next: string | null) {
    setKind(next); setValues({}); setError("");
  }

  async function save(e: React.FormEvent) {
    e.preventDefault();
    if (!spec) return;
    setError(""); setSaving(true);
    try {
      if (editing) {
        await api.patch(`/connections/${editing.id}`, { label, values });
        onSaved(editing.id);
      } else {
        const defaults = Object.fromEntries(spec.fields.filter((f) => f.default).map((f) => [f.name, f.default]));
        const { id } = await api.post<{ id: string }>("/connections", { kind: spec.kind, label, values: { ...defaults, ...values } });
        onSaved(id);
      }
      ref.current?.close();
    } catch (err) { setError((err as Error).message); }
    finally { setSaving(false); }
  }

  return (
    <Sheet ref={ref}
      title={spec ? <span className="flex items-center gap-2.5"><KindMark kind={spec.kind} size="sm" />{editing ? `Edit ${editing.label}` : spec.name}<VerifiedBadge verified={spec.verified} /></span> : "Add a connection"}
      description={spec ? spec.description : "Choose the platform to connect. Nexus only ever reads from it."}
      onBack={spec && !editing ? () => choose(null) : undefined}
      footer={spec && <>
        {spec.docs_url && (
          <a href={spec.docs_url} target="_blank" rel="noreferrer" className="mr-auto inline-flex items-center gap-1 self-center text-caption text-muted-foreground hover:text-foreground">
            Setup guide<ExternalLink className="size-3" />
          </a>
        )}
        <Button type="button" variant="ghost" onClick={() => editing ? ref.current?.close() : choose(null)}>{editing ? "Cancel" : "Back"}</Button>
        <Button form="connection-form" disabled={saving}>{saving && <Loader2 className="animate-spin" />}{editing ? "Save changes" : "Add connection"}</Button>
      </>}>
      {!spec ? (
        <div className="space-y-4">
          <div className="relative">
            <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input className="pl-9" placeholder={`Search ${specs.length} platforms`} value={search} onChange={(e) => setSearch(e.target.value)} />
          </div>
          <div className="grid gap-2 sm:grid-cols-2">
            {shown.map((s) => (
              <button type="button" key={s.kind} onClick={() => choose(s.kind)}
                className="group flex items-start gap-3 rounded-lg border border-border p-3.5 text-left transition-colors hover:border-primary/40 hover:bg-primary-soft/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
                <KindMark kind={s.kind} />
                <span className="min-w-0 flex-1">
                  <span className="flex flex-wrap items-center gap-1.5">
                    <span className="text-body font-medium text-foreground">{s.name}</span>
                    <VerifiedBadge verified={s.verified} />
                  </span>
                  <span className="mt-1 line-clamp-3 text-caption leading-relaxed text-muted-foreground">{s.description}</span>
                </span>
                <ChevronRight className="mt-2 size-4 shrink-0 text-muted-foreground transition-transform group-hover:translate-x-0.5" />
              </button>
            ))}
          </div>
          {shown.length === 0 && <p className="py-6 text-center text-body text-muted-foreground">No platform matches “{search}”.</p>}
          <p className="text-caption text-muted-foreground">
            Verified platforms ({verified} of {specs.length}) are tested end to end against real servers. Beta platforms follow
            the vendor&apos;s documentation and have not yet been run against a real account.
          </p>
        </div>
      ) : (
        <form id="connection-form" className="space-y-4" onSubmit={save}>
          {!spec.verified && !editing && (
            <Callout tone="info">This platform is in beta. Test the connection after adding it; the test reports each step.</Callout>
          )}
          <Field label="Name" hint="How this connection appears in Nexus.">
            <Input required autoFocus value={label} onChange={(e) => setLabel(e.target.value)} placeholder="Sales warehouse" />
          </Field>
          {spec.fields.map((f) => {
            const saved = !!editing && f.secret && editing.secrets_saved.includes(f.name);
            return (
              <Field key={f.name} label={f.label} optional={!f.required} hint={saved ? "Saved. Leave blank to keep it." : f.help || undefined}>
                {f.options.length ? (
                  <Select value={values[f.name] ?? f.default} onChange={(e) => setValues({ ...values, [f.name]: e.target.value })}>
                    {f.options.map((o) => <option key={o} value={o}>{o}</option>)}
                  </Select>
                ) : f.multiline ? (
                  <Textarea rows={4} className="font-mono text-caption" placeholder={saved ? "••••••••" : undefined}
                    value={values[f.name] ?? ""} onChange={(e) => setValues({ ...values, [f.name]: e.target.value })} />
                ) : (
                  <Input type={f.secret ? "password" : "text"} required={f.required && !f.default && !saved}
                    placeholder={saved ? "••••••••" : f.placeholder || f.default} autoComplete={f.secret ? "new-password" : "off"}
                    value={values[f.name] ?? ""} onChange={(e) => setValues({ ...values, [f.name]: e.target.value })} />
                )}
              </Field>
            );
          })}
          <p className="text-caption text-muted-foreground">Credentials are encrypted for this workspace and never shown again.</p>
          {error && <Callout tone="danger">{error}</Callout>}
        </form>
      )}
    </Sheet>
  );
}

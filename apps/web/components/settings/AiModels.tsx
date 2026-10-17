"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Bot, KeyRound, Plug, Plus, Power, Sparkles, Star, Trash2, Zap } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Callout } from "@/components/ui/callout";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { Dialog } from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { Field, Input, Select } from "@/components/ui/form";
import { StatusPill } from "@/components/ui/status-pill";
import { Table, Td, Th, Tr } from "@/components/ui/table";
import { api } from "@/lib/api";
import { when } from "@/lib/format";

type Preset = { kind: string; label: string; base_url: string | null; needs_key: boolean; hint: string };
type Model = {
  id: string; model: string; label: string; price_in_per_mtok: string | null; price_out_per_mtok: string | null;
  is_default: boolean; enabled: boolean;
};
type Provider = {
  id: string; kind: string; label: string; base_url: string | null; key_last4: string | null; has_key: boolean;
  enabled: boolean; last_test_ok: boolean | null; last_test_at: string | null; last_test_msg: string | null;
  models: Model[];
};

const KIND_NAME: Record<string, string> = {
  anthropic: "Anthropic", openai: "OpenAI", google: "Google Gemini", openai_compatible: "OpenAI-compatible",
};

function ModelRow({ m, onChange }: { m: Model; onChange: () => void }) {
  const [editing, setEditing] = useState(false);
  const [price, setPrice] = useState({ inp: m.price_in_per_mtok ?? "", out: m.price_out_per_mtok ?? "" });
  async function patch(body: object) {
    await api.patch(`/ai/models/${m.id}`, body);
    onChange();
  }
  async function savePrice() {
    const clear = price.inp === "" && price.out === "";
    await patch(clear ? { clear_price: true } : { price_in_per_mtok: Number(price.inp), price_out_per_mtok: Number(price.out) });
    setEditing(false);
  }
  return (
    <Tr className={m.enabled ? "" : "opacity-55"}>
      <Td>
        <div className="font-medium text-foreground">{m.label}</div>
        <div className="font-mono text-caption text-muted-foreground">{m.model}</div>
      </Td>
      <Td>
        {editing ? (
          <div className="flex items-center gap-1.5">
            <Input className="h-8 w-20" placeholder="in" value={price.inp} onChange={(e) => setPrice({ ...price, inp: e.target.value })} />
            <Input className="h-8 w-20" placeholder="out" value={price.out} onChange={(e) => setPrice({ ...price, out: e.target.value })} />
            <Button size="sm" onClick={savePrice}>Save</Button>
          </div>
        ) : (
          <button className="text-body text-muted-foreground hover:text-foreground" onClick={() => setEditing(true)}>
            {m.price_in_per_mtok ? <span className="num">${Number(m.price_in_per_mtok)} / ${Number(m.price_out_per_mtok)} per M tokens</span> : "Not priced · set price"}
          </button>
        )}
      </Td>
      <Td>
        {m.is_default ? <StatusPill tone="primary" icon={<Star />}>Default</StatusPill>
          : <Button variant="ghost" size="sm" disabled={!m.enabled} onClick={() => patch({ is_default: true })}>Make default</Button>}
      </Td>
      <Td className="whitespace-nowrap text-right">
        <Button variant="ghost" size="sm" onClick={() => patch({ enabled: !m.enabled })}><Power />{m.enabled ? "Turn off" : "Turn on"}</Button>
        <Button variant="ghost" size="sm" className="hover:text-danger" onClick={async () => {
          if (confirm(`Remove ${m.label}? Past runs keep their record of which model ran.`)) { await api.del(`/ai/models/${m.id}`); onChange(); }
        }}><Trash2 /></Button>
      </Td>
    </Tr>
  );
}

function ProviderCard({ p, onChange }: { p: Provider; onChange: () => void }) {
  const [testing, setTesting] = useState(false);
  const [available, setAvailable] = useState<string[] | null>(null);
  const [listError, setListError] = useState("");
  const [newModel, setNewModel] = useState({ model: "", label: "" });
  const [newKey, setNewKey] = useState("");
  const [error, setError] = useState("");

  async function test() {
    setTesting(true);
    try { await api.post(`/ai/providers/${p.id}/test`); } finally { setTesting(false); onChange(); }
  }
  async function loadAvailable() {
    setListError("");
    try { setAvailable(await api.get<string[]>(`/ai/providers/${p.id}/available-models`)); }
    catch (e) { setListError((e as Error).message); }
  }
  async function addModel(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    try {
      await api.post("/ai/models", { provider_id: p.id, model: newModel.model.trim(), label: newModel.label.trim() });
      setNewModel({ model: "", label: "" });
      onChange();
    } catch (err) { setError((err as Error).message); }
  }
  async function replaceKey(e: React.FormEvent) {
    e.preventDefault();
    await api.patch(`/ai/providers/${p.id}`, { api_key: newKey });
    setNewKey("");
    onChange();
  }

  return (
    <Card className={p.enabled ? "" : "opacity-70"}>
      <CardHeader icon={<Bot />} title={p.label}
        description={<>{KIND_NAME[p.kind]}{p.base_url ? ` · ${p.base_url}` : ""}{p.has_key ? ` · key ending ${p.key_last4 || "••••"}` : " · no key"}</>}
        actions={<>
          <Button variant="outline" size="sm" disabled={testing || !p.models.length} onClick={test}><Zap />{testing ? "Testing…" : "Test"}</Button>
          <Button variant="ghost" size="sm" onClick={async () => { await api.patch(`/ai/providers/${p.id}`, { enabled: !p.enabled }); onChange(); }}>
            <Power />{p.enabled ? "Turn off" : "Turn on"}
          </Button>
          <Button variant="ghost" size="sm" className="hover:text-danger" title="Remove" onClick={async () => {
            if (confirm(`Remove ${p.label} and its models?`)) { await api.del(`/ai/providers/${p.id}`); onChange(); }
          }}><Trash2 /></Button>
        </>} />
      <CardBody className="space-y-4">
        {p.last_test_at && (
          <Callout tone={p.last_test_ok ? "success" : "danger"}>
            {p.last_test_msg} <span className="opacity-70">({when(p.last_test_at)})</span>
          </Callout>
        )}
        {p.models.length > 0 && (
          <div className="rounded-md border border-border">
            <Table>
              <thead><tr><Th>Model</Th><Th>Price</Th><Th /><Th /></tr></thead>
              <tbody>{p.models.map((m) => <ModelRow key={m.id} m={m} onChange={onChange} />)}</tbody>
            </Table>
          </div>
        )}
        <form className="flex flex-wrap items-end gap-3" onSubmit={addModel}>
          <Field label="Add a model" className="min-w-[220px] flex-1">
            <Input required list={`models-${p.id}`} placeholder="Model id" value={newModel.model}
              onFocus={() => available === null && loadAvailable()}
              onChange={(e) => setNewModel({ ...newModel, model: e.target.value })} />
            <datalist id={`models-${p.id}`}>{(available ?? []).map((m) => <option key={m} value={m} />)}</datalist>
          </Field>
          <Field label="Display name" optional className="min-w-[180px] flex-1">
            <Input value={newModel.label} onChange={(e) => setNewModel({ ...newModel, label: e.target.value })} />
          </Field>
          <Button><Plus />Add model</Button>
        </form>
        {listError && <p className="text-caption text-danger">Could not list this provider&apos;s models: {listError}</p>}
        {available && <p className="text-caption text-muted-foreground">{available.length} models available with this key. Start typing to pick one.</p>}
        {error && <Callout tone="danger">{error}</Callout>}
        {p.kind !== "openai_compatible" && (
          <form className="flex flex-wrap items-end gap-3 border-t border-border pt-4" onSubmit={replaceKey}>
            <Field label="Replace API key" className="min-w-[220px] flex-1">
              <Input type="password" autoComplete="off" placeholder="New key" value={newKey} onChange={(e) => setNewKey(e.target.value)} />
            </Field>
            <Button variant="outline" disabled={newKey.length < 8}><KeyRound />Save key</Button>
          </form>
        )}
      </CardBody>
    </Card>
  );
}

export default function AiModels() {
  const [providers, setProviders] = useState<Provider[] | null>(null);
  const [presets, setPresets] = useState<Preset[]>([]);
  const [form, setForm] = useState({ preset: 0, label: "", base_url: "", api_key: "" });
  const [error, setError] = useState("");
  const dialog = useRef<HTMLDialogElement>(null);

  const load = useCallback(() => api.get<Provider[]>("/ai/providers").then(setProviders), []);
  useEffect(() => {
    load();
    api.get<Preset[]>("/ai/presets").then(setPresets);
  }, [load]);

  const preset = presets[form.preset];

  function choose(i: number) {
    setForm({ preset: i, label: presets[i].label, base_url: presets[i].base_url ?? "", api_key: "" });
  }

  async function add(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    try {
      await api.post("/ai/providers", {
        kind: preset.kind, label: form.label || preset.label,
        base_url: form.base_url || null, api_key: form.api_key || null,
      });
      dialog.current?.close();
      load();
    } catch (err) { setError((err as Error).message); }
  }

  const open = () => { if (presets.length) choose(0); setError(""); dialog.current?.showModal(); };

  return (
    <section className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-h2 text-foreground">AI models</h2>
          <p className="text-body text-muted-foreground">Connect your own AI accounts. Keys are encrypted and never shown again.</p>
        </div>
        <Button onClick={open}><Plus />Add a provider</Button>
      </div>
      {providers === null ? <Card><CardBody className="text-muted-foreground">Loading…</CardBody></Card> : providers.length === 0 ? (
        <Card>
          <EmptyState icon={Sparkles} title="No AI connected yet"
            description="Add a provider (Claude, GPT, Gemini, or a model on your own server), then the models your team may use."
            action={<Button onClick={open}><Plug />Add a provider</Button>} />
        </Card>
      ) : providers.map((p) => <ProviderCard key={p.id} p={p} onChange={load} />)}

      <Dialog ref={dialog} title="Add an AI provider" description="Keys are stored encrypted and never returned.">
        {preset && (
          <form className="space-y-4" onSubmit={add}>
            <Field label="Provider" hint={preset.hint}>
              <Select value={form.preset} onChange={(e) => choose(Number(e.target.value))}>
                {presets.map((p, i) => <option key={i} value={i}>{p.label}</option>)}
              </Select>
            </Field>
            <Field label="Name shown to your team"><Input value={form.label} onChange={(e) => setForm({ ...form, label: e.target.value })} /></Field>
            {preset.kind === "openai_compatible" && (
              <Field label="Endpoint URL"><Input required value={form.base_url} placeholder="https://…/v1" onChange={(e) => setForm({ ...form, base_url: e.target.value })} /></Field>
            )}
            {(preset.needs_key || preset.kind === "openai_compatible") && (
              <Field label="API key" optional={!preset.needs_key} hint={!preset.needs_key ? "Not needed for a model on your own machine." : undefined}>
                <Input type="password" autoComplete="off" required={preset.needs_key} value={form.api_key} onChange={(e) => setForm({ ...form, api_key: e.target.value })} />
              </Field>
            )}
            {error && <Callout tone="danger">{error}</Callout>}
            <div className="flex justify-end gap-2 pt-1">
              <Button type="button" variant="ghost" onClick={() => dialog.current?.close()}>Cancel</Button>
              <Button>Add provider</Button>
            </div>
          </form>
        )}
      </Dialog>
    </section>
  );
}

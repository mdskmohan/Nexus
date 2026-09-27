"use client";

import { useCallback, useEffect, useRef, useState } from "react";
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
    <tr style={{ opacity: m.enabled ? 1 : 0.55 }}>
      <td>
        <div style={{ fontWeight: 600 }}>{m.label}</div>
        <div className="faint mono">{m.model}</div>
      </td>
      <td>
        {editing ? (
          <div className="row" style={{ gap: 6 }}>
            <input style={{ width: 90 }} placeholder="in" value={price.inp} onChange={(e) => setPrice({ ...price, inp: e.target.value })} />
            <input style={{ width: 90 }} placeholder="out" value={price.out} onChange={(e) => setPrice({ ...price, out: e.target.value })} />
            <button className="btn-small" onClick={savePrice}>Save</button>
          </div>
        ) : (
          <button className="btn-quiet btn-small" style={{ padding: 0 }} onClick={() => setEditing(true)}>
            {m.price_in_per_mtok ? `$${Number(m.price_in_per_mtok)} / $${Number(m.price_out_per_mtok)} per M tokens` : "Not priced — set price"}
          </button>
        )}
      </td>
      <td>
        {m.is_default ? <span className="pill pill-brand">Default</span>
          : <button className="btn-quiet btn-small" disabled={!m.enabled} onClick={() => patch({ is_default: true })}>Make default</button>}
      </td>
      <td style={{ textAlign: "right", whiteSpace: "nowrap" }}>
        <button className="btn-quiet btn-small" onClick={() => patch({ enabled: !m.enabled })}>{m.enabled ? "Turn off" : "Turn on"}</button>
        <button className="btn-quiet btn-small" onClick={async () => {
          if (confirm(`Remove ${m.label}? Past tasks keep their record of which model ran.`)) { await api.del(`/ai/models/${m.id}`); onChange(); }
        }}>Remove</button>
      </td>
    </tr>
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
    <div className="card" style={{ opacity: p.enabled ? 1 : 0.7 }}>
      <div className="card-head">
        <div>
          <h3>{p.label}</h3>
          <div className="faint">
            {KIND_NAME[p.kind]}{p.base_url ? ` · ${p.base_url}` : ""}{p.has_key ? ` · key ending ${p.key_last4 || "••••"}` : " · no key"}
          </div>
        </div>
        <div className="row" style={{ gap: 6 }}>
          <button className="btn-small" disabled={testing || !p.models.length} onClick={test}>{testing ? "Testing…" : "Test connection"}</button>
          <button className="btn-quiet btn-small" onClick={async () => { await api.patch(`/ai/providers/${p.id}`, { enabled: !p.enabled }); onChange(); }}>
            {p.enabled ? "Turn off" : "Turn on"}
          </button>
          <button className="btn-quiet btn-small" onClick={async () => {
            if (confirm(`Remove ${p.label} and its models?`)) { await api.del(`/ai/providers/${p.id}`); onChange(); }
          }}>Remove</button>
        </div>
      </div>
      <div className="card-pad stack" style={{ gap: 12 }}>
        {p.last_test_at && (
          <div className={`notice ${p.last_test_ok ? "notice-ok" : "notice-bad"}`} style={{ padding: "8px 12px" }}>
            <p>{p.last_test_msg} <span className="faint" style={{ color: "inherit" }}>({when(p.last_test_at)})</span></p>
          </div>
        )}
        {p.models.length > 0 && (
          <table>
            <thead><tr><th>Model</th><th>Price</th><th></th><th></th></tr></thead>
            <tbody>{p.models.map((m) => <ModelRow key={m.id} m={m} onChange={onChange} />)}</tbody>
          </table>
        )}
        <form className="row" onSubmit={addModel} style={{ alignItems: "flex-end" }}>
          <label className="grow">Add a model
            <input required list={`models-${p.id}`} placeholder="Model id, e.g. from the list" value={newModel.model}
                   onFocus={() => available === null && loadAvailable()}
                   onChange={(e) => setNewModel({ ...newModel, model: e.target.value })} />
            <datalist id={`models-${p.id}`}>{(available ?? []).map((m) => <option key={m} value={m} />)}</datalist>
          </label>
          <label className="grow">Display name <span className="hint">Optional</span>
            <input value={newModel.label} onChange={(e) => setNewModel({ ...newModel, label: e.target.value })} />
          </label>
          <button className="btn-primary">Add model</button>
        </form>
        {listError && <p className="faint" style={{ color: "var(--bad)" }}>Could not list this provider&apos;s models: {listError}</p>}
        {available && <p className="faint">{available.length} models available with this key. Start typing to pick one.</p>}
        {error && <div className="notice notice-bad"><p>{error}</p></div>}
        {p.kind !== "openai_compatible" && (
          <form className="row" onSubmit={replaceKey} style={{ alignItems: "flex-end" }}>
            <label className="grow">Replace API key
              <input type="password" autoComplete="off" placeholder="New key" value={newKey} onChange={(e) => setNewKey(e.target.value)} />
            </label>
            <button disabled={newKey.length < 8}>Save key</button>
          </form>
        )}
      </div>
    </div>
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

  return (
    <section className="stack">
      <div className="row" style={{ justifyContent: "space-between" }}>
        <div>
          <h2>AI models</h2>
          <p className="muted">Connect your firm&apos;s own AI accounts. Keys are encrypted and never shown again after you save them.</p>
        </div>
        <button className="btn-primary" onClick={() => { if (presets.length) choose(0); setError(""); dialog.current?.showModal(); }}>Add a provider</button>
      </div>
      {providers === null ? <div className="card empty">Loading…</div> : providers.length === 0 ? (
        <div className="card empty stack" style={{ alignItems: "center" }}>
          <h3>No AI connected yet</h3>
          <p>Add a provider (Claude, GPT, Gemini, or a model running on your own server), then add the models your team may use.</p>
        </div>
      ) : providers.map((p) => <ProviderCard key={p.id} p={p} onChange={load} />)}

      <dialog ref={dialog}>
        {preset && (
          <form className="card-pad stack" onSubmit={add}>
            <h2>Add an AI provider</h2>
            <label>Provider
              <select value={form.preset} onChange={(e) => choose(Number(e.target.value))}>
                {presets.map((p, i) => <option key={i} value={i}>{p.label}</option>)}
              </select>
              <span className="hint">{preset.hint}</span>
            </label>
            <label>Name shown to your team<input value={form.label} onChange={(e) => setForm({ ...form, label: e.target.value })} /></label>
            {preset.kind === "openai_compatible" && (
              <label>Endpoint URL<input required value={form.base_url} placeholder="https://…/v1" onChange={(e) => setForm({ ...form, base_url: e.target.value })} /></label>
            )}
            {(preset.needs_key || preset.kind === "openai_compatible") && (
              <label>API key {!preset.needs_key && <span className="hint">Not needed for a model on your own machine</span>}
                <input type="password" autoComplete="off" required={preset.needs_key} value={form.api_key} onChange={(e) => setForm({ ...form, api_key: e.target.value })} />
              </label>
            )}
            {error && <div className="notice notice-bad"><p>{error}</p></div>}
            <div className="row" style={{ justifyContent: "flex-end" }}>
              <button type="button" className="btn-quiet" onClick={() => dialog.current?.close()}>Cancel</button>
              <button className="btn-primary">Add provider</button>
            </div>
          </form>
        )}
      </dialog>
    </section>
  );
}

"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";

export type ModelChoice = { id: string; label: string; provider: string; kind: string; model: string; is_default: boolean };

// The AI model for one task. Defaults to the firm's default; hidden when there is only one choice.
export default function ModelPicker({ value, onChange }: { value: string; onChange: (id: string) => void }) {
  const [models, setModels] = useState<ModelChoice[] | null>(null);
  useEffect(() => {
    api.get<ModelChoice[]>("/ai/models").then((m) => {
      setModels(m);
      if (!value && m.length) onChange(m[0].id);
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  if (!models || models.length < 2) return null;
  return (
    <label>AI model
      <select value={value} onChange={(e) => onChange(e.target.value)}>
        {models.map((m) => <option key={m.id} value={m.id}>{m.label} · {m.provider}{m.is_default ? " (firm default)" : ""}</option>)}
      </select>
    </label>
  );
}

// Thin client for the Nexus API. Requests go to /api on this origin and are
// proxied to the API server (see next.config.ts), so the session cookie is
// first-party and never readable by scripts.

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const init: RequestInit = {
    method,
    credentials: "same-origin",
    headers: { "x-nexus-client": "web" },
  };
  if (body instanceof FormData) {
    init.body = body;
  } else if (body !== undefined) {
    init.body = JSON.stringify(body);
    (init.headers as Record<string, string>)["content-type"] = "application/json";
  }
  const res = await fetch(`/api${path}`, init);
  if (!res.ok) {
    let message = "Something went wrong. Please try again.";
    try {
      const data = await res.json();
      if (typeof data.detail === "string") message = data.detail;
      else if (Array.isArray(data.detail)) message = data.detail.map((d: { msg: string }) => d.msg).join(" ");
    } catch {}
    throw new ApiError(res.status, message);
  }
  return res.status === 204 ? (undefined as T) : res.json();
}

export const api = {
  get: <T>(path: string) => request<T>("GET", path),
  post: <T>(path: string, body?: unknown) => request<T>("POST", path, body ?? {}),
  put: <T>(path: string, body: unknown) => request<T>("PUT", path, body),
  patch: <T>(path: string, body: unknown) => request<T>("PATCH", path, body),
  del: <T>(path: string) => request<T>("DELETE", path),
};

export type Role = "admin" | "partner" | "associate" | "paralegal";
export const ROLE_ORDER: Role[] = ["paralegal", "associate", "partner", "admin"];
export const atLeast = (role: Role, needed: Role) => ROLE_ORDER.indexOf(role) >= ROLE_ORDER.indexOf(needed);

export type Me = {
  user: { id: string; name: string; email: string; role: Role };
  firm: { id: string; name: string; preferences: string };
  model_configured: boolean;
};

export type Matter = {
  id: string; name: string; client_name: string; description: string; status: "open" | "closed";
  created_at: string; documents?: number; tasks?: number; awaiting_review?: number; last_activity?: string;
};

export type DocFlags = {
  hidden_instruction_count?: number;
  hidden_instructions?: { seq: number; page: number; why: string; excerpt: string }[];
  sensitive?: Record<string, number>;
};

export type Doc = {
  id: string; filename: string; content_type: string; size_bytes: number;
  status: "queued" | "processing" | "ready" | "failed"; page_count: number | null; error: string | null;
  flags: DocFlags; created_at: string; uploaded_by?: string;
};

export type Passage = { id: string; seq: number; page: number; heading: string; text: string };

export type Citation = {
  passage_id: string; quote: string; verified: boolean; document_id?: string; document?: string;
  page?: number; position?: number; heading?: string; location?: string; reason?: string;
};

export type Finding = {
  position_id: string; title: string; status: "meets" | "deviates" | "missing" | "unclear";
  risk: "high" | "medium" | "low"; explanation: string; suggested_language: string; citation: Citation | null;
};

export type RunStatus = "queued" | "running" | "needs_review" | "approved" | "rejected" | "failed" | "cancelled";

export type Step = {
  seq: number; kind: string; title: string; status: "ok" | "warning" | "blocked" | "error";
  detail: Record<string, unknown>; duration_ms: number | null; created_at: string;
};

export type Run = {
  id: string; matter_id: string; matter_name?: string; kind: "ask" | "review" | "draft"; status: RunStatus; title: string;
  created_at: string; started_at: string | null; finished_at: string | null; cost_usd: string;
  guardrails: {
    citations_checked?: number; citations_verified?: number; statements_removed?: number;
    sent_back_to_fix?: number; positions_covered?: number; positions_total?: number; unverified_markers?: number;
  };
  created_by_name: string | null; reviewed_by_name: string | null; reviewed_at: string | null;
  input?: Record<string, string>;
  output?: AskOutput & ReviewOutput & DraftOutput;
  error?: string | null; review_note?: string | null; model?: string | null;
  input_tokens?: number; output_tokens?: number; cache_read_tokens?: number;
  steps?: Step[]; files?: { id: string; filename: string }[];
};

export type AskOutput = {
  answer: { text: string; citations: Citation[] }[];
  removed: { text: string; reason: string }[];
  could_not_answer: string;
};

export type ReviewOutput = {
  document_id: string;
  playbook: { slug: string; name: string; validated_by: string | null; is_starter: boolean };
  client_role: string; summary: string; client_note: string;
  findings: Finding[]; issues: Finding[]; redline_not_placed?: string[];
};

export type DraftOutput = {
  summary: string; instructions: string;
  deliverables: { filename: string; content: string; sources: (Citation & { id: string })[]; unverified: string[] }[];
};

export type Position = {
  id: string; title: string; standard: string; fallback: string; red_flags: string; severity: "high" | "medium" | "low";
};

export type Playbook = {
  id: string; slug: string; name: string; description: string; document_type: string; is_starter: boolean;
  validated_by: string | null; validated_at: string | null; position_count?: number; positions?: Position[];
  updated_at: string;
};

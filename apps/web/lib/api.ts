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

export type Role = "admin" | "steward" | "developer" | "analyst" | "viewer";
export const ROLES: Role[] = ["admin", "steward", "developer", "analyst", "viewer"];

export type Permission =
  | "manage_workspace" | "manage_people" | "manage_ai" | "manage_connections" | "approve_graph"
  | "approve_runs" | "build_agents" | "run_agents" | "use_apps" | "view_audit";

export type Me = {
  user: { id: string; name: string; email: string; role: Role };
  workspace: { id: string; name: string };
  permissions: Permission[];
  model_configured: boolean;
};

export const can = (me: Me, permission: Permission) => me.permissions.includes(permission);

export type RunStatus = "queued" | "running" | "waiting" | "succeeded" | "failed" | "cancelled";

export type Step = {
  seq: number; kind: string; title: string; status: "ok" | "warning" | "blocked" | "error";
  detail: Record<string, unknown>; duration_ms: number | null; created_at: string;
};

export type HumanRequest = {
  id: string; run_id: string; kind: "approval" | "clarification"; title: string;
  shown: Record<string, unknown>; permission: Permission; created_at: string;
  run_title?: string; requested_for_name?: string | null;
};

export type Run = {
  id: string; kind: string; status: RunStatus; title: string; error: string | null;
  model: string | null; cost_usd: string; created_at: string; started_at: string | null; finished_at: string | null;
  created_by_name: string | null; steps?: Step[];
};

export type SpecField = {
  name: string; label: string; required: boolean; secret: boolean; multiline: boolean;
  help: string; placeholder: string; default: string; options: string[];
};
export type ConnectorSpec = { kind: string; name: string; description: string; docs_url: string; verified: boolean; fields: SpecField[] };

export type Connection = {
  id: string; kind: string; label: string; config: Record<string, string>; secrets_saved: string[]; verified: boolean;
  last_test_ok: boolean | null; last_test_at: string | null; last_test_msg: string | null;
  collect_status: "never" | "queued" | "running" | "done" | "failed"; collected_at: string | null; collect_msg: string | null;
  created_at: string;
  last_run: CollectRun | null;
  last_success: { id: string; stats: CollectStats; finished_at: string } | null;
};

export type CollectRunStatus = "queued" | "running" | "succeeded" | "failed" | "cancelled";
export type CollectPhase = "queued" | "connect" | "discover" | "keys" | "graph" | "joins" | "done";
export type CollectStats = Partial<Record<
  "schemas" | "schemas_read" | "schemas_total" | "tables" | "views" | "columns" | "foreign_keys" | "tables_saved"
  | "new_tables" | "known_tables" | "removed_tables" | "joins_suggested" | "seconds", number>>;

export type CollectRun = {
  id: string; connection_id: string; trigger: "manual" | "retry" | "setup" | "schedule";
  status: CollectRunStatus; phase: CollectPhase; progress: number; stats: CollectStats;
  error: string | null; error_kind: string | null; hint: string | null; cancel_requested: boolean;
  created_at: string; started_at: string | null; finished_at: string | null; updated_at: string;
  connection_label?: string; connection_kind?: string; requested_by_name?: string | null;
};

export type RunLogLine = {
  id: number; at: string; level: "info" | "success" | "warning" | "error"; message: string;
  data: Record<string, unknown> | null;
};

export type RunsSummary = { active: number; succeeded_24h: number; failed_24h: number; total: number };

export type ItemKind = "table" | "column" | "join" | "entity" | "metric";
export type ItemStatus = "proposed" | "approved" | "rejected" | "deprecated";

export type KgItem = {
  id: string; kind: ItemKind; key: string; name: string; description: string; attrs: Record<string, any>;
  status: ItemStatus; origin: "discovered" | "suggested" | "person"; connection_id: string | null;
  connection_label: string | null; parent_id: string | null; approved_in: number | null; deprecated_in: number | null;
  missing_since: string | null; review_note: string | null; reviewed_at: string | null; reviewed_by_name: string | null;
  proposed_by_name: string | null; created_at: string;
  columns?: KgItem[]; joins?: KgItem[];
};

export type GraphSummary = { version: number; counts: Partial<Record<ItemKind, Partial<Record<ItemStatus, number>>>>; missing: number };
export type JoinPath = { hops: number; joins: { id: string; name: string; cross_source: boolean }[] };

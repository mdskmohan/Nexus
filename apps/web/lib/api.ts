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

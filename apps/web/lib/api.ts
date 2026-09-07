/**
 * Client for the Nexus API.
 *
 * Connection configurations carry secrets, so they are POSTed and never cached,
 * never placed in a URL, and never written to localStorage.
 */

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"

export interface ConnectorField {
  name: string
  label: string
  type: "text" | "secret" | "number" | "select" | "textarea" | "boolean"
  required: boolean
  help: string | null
  placeholder: string | null
  options: string[]
  default: string | null
}

export interface Connector {
  id: string
  name: string
  category: string
  description: string
  docs_url: string | null
  /** False when this connector has not yet been exercised against a real account. */
  verified: boolean
  /** False when the server lacks the driver — a different problem from bad credentials. */
  driver_available: boolean
  driver_package: string | null
  fields: ConnectorField[]
}

export interface ConnectionTestResult {
  ok: boolean
  message: string
  details: Record<string, string>
}

export class ApiError extends Error {}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${BASE}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...init?.headers },
      cache: "no-store",
    })
  } catch {
    // A dead API and a rejected request need different messages: one is "start
    // the server", the other is "fix your input".
    throw new ApiError(
      `Could not reach the Nexus API at ${BASE}. Is it running?`
    )
  }
  if (!response.ok) {
    const detail = await response.text().catch(() => "")
    throw new ApiError(detail || `Request failed with ${response.status}`)
  }
  return (await response.json()) as T
}

export function listConnectors(): Promise<Connector[]> {
  return request<Connector[]>("/api/v1/connectors")
}

export function testConnection(
  connectorId: string,
  config: Record<string, string>
): Promise<ConnectionTestResult> {
  return request<ConnectionTestResult>("/api/v1/connections/test", {
    method: "POST",
    body: JSON.stringify({ connector_id: connectorId, config }),
  })
}

/** Human labels for the category groups shown in the connections list. */
export const CATEGORY_LABELS: Record<string, string> = {
  warehouse: "Data warehouses",
  lakehouse: "Lakehouse",
  transformation: "Transformation",
  orchestration: "Orchestration",
  version_control: "Version control",
  lineage: "Lineage",
  database: "Databases",
}

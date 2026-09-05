/**
 * Domain types for the web client.
 *
 * These mirror the API's Pydantic models in services/api/nexus. When the API
 * contract changes, this file changes with it — it is the single place the
 * frontend's understanding of the domain lives.
 */

export type Severity = "critical" | "high" | "medium" | "low"
export type RunState = "success" | "running" | "failed" | "queued"
export type Criticality = "critical" | "high" | "medium" | "low"

/** Autonomy levels from ADR-003. The policy engine gates actions against these. */
export type AutonomyLevel = 0 | 1 | 2 | 3 | 4

export interface Pipeline {
  id: string
  name: string
  description: string
  criticality: Criticality
  owner: { team: string; oncall?: string }
  target: { warehouse: string; orchestrator: string }
  schedule: { cron: string; humanized: string }
  lastRun: { state: RunState; startedAt: string; durationSeconds: number }
  modelCount: number
  consumerCount: number
  /** Whether Nexus generated this pipeline or lifted it from the customer's estate. */
  origin: "created" | "adopted"
}

/** A single sourced, timestamped fact supporting or contradicting a hypothesis. */
export interface Evidence {
  id: string
  summary: string
  detail: string
  /** Where the fact came from — shown so an engineer can verify it independently. */
  source: string
  observedAt: string
  supports: boolean
}

export interface Hypothesis {
  id: string
  title: string
  /** 0-1. Derived from evidence weight, never asserted by the model directly. */
  confidence: number
  evidence: Evidence[]
}

export interface ImpactedEntity {
  id: string
  name: string
  kind: "model" | "dashboard" | "export" | "ml_feature"
  criticality: Criticality
}

export interface Remediation {
  id: string
  summary: string
  rationale: string
  diff: string
  /** Autonomy level this action requires before it may execute. */
  requiredLevel: AutonomyLevel
  validation: {
    ran: boolean
    testsPassed: number
    testsTotal: number
    sandbox: string
  }
}

export interface Incident {
  id: string
  number: number
  title: string
  severity: Severity
  status: "investigating" | "diagnosed" | "awaiting_approval" | "resolved"
  pipelineId: string
  pipelineName: string
  detectedAt: string
  failedNode: string
  hypotheses: Hypothesis[]
  impact: ImpactedEntity[]
  remediation?: Remediation
}

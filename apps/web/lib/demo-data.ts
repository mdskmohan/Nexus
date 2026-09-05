/**
 * Demo fixtures.
 *
 * Stands in for the API while the backend is under construction. The shapes are
 * the real ones from lib/types.ts, so swapping in live data is a fetch call, not
 * a rewrite. The incident below is the reference scenario: an upstream type change
 * in Salesforce breaking a downstream join.
 */

import type { Incident, Pipeline } from "@/lib/types"

const MINUTE = 60_000

/** Fixed clock so the UI is deterministic across reloads and screenshots. */
export const NOW = new Date("2026-09-05T09:12:00Z")

const ago = (minutes: number) => new Date(NOW.getTime() - minutes * MINUTE).toISOString()

export const pipelines: Pipeline[] = [
  {
    id: "customer_360",
    name: "Customer 360",
    description: "Unified customer dimension from Salesforce and application Postgres",
    criticality: "high",
    owner: { team: "data-platform", oncall: "@data-oncall" },
    target: { warehouse: "Snowflake", orchestrator: "Airflow" },
    schedule: { cron: "0 6 * * *", humanized: "Daily at 06:00 UTC" },
    lastRun: { state: "failed", startedAt: ago(41), durationSeconds: 214 },
    modelCount: 3,
    consumerCount: 1,
    origin: "created",
  },
  {
    id: "revenue_daily",
    name: "Revenue Daily",
    description: "Daily recognised revenue by product line and region",
    criticality: "critical",
    owner: { team: "finance-data", oncall: "@finance-oncall" },
    target: { warehouse: "Snowflake", orchestrator: "Airflow" },
    schedule: { cron: "0 5 * * *", humanized: "Daily at 05:00 UTC" },
    lastRun: { state: "success", startedAt: ago(252), durationSeconds: 486 },
    modelCount: 12,
    consumerCount: 4,
    origin: "created",
  },
  {
    id: "product_events",
    name: "Product Events",
    description: "Clickstream sessionisation from Kafka into the events mart",
    criticality: "medium",
    owner: { team: "growth-data" },
    target: { warehouse: "Databricks", orchestrator: "Airflow" },
    schedule: { cron: "0 * * * *", humanized: "Hourly" },
    lastRun: { state: "running", startedAt: ago(6), durationSeconds: 372 },
    modelCount: 8,
    consumerCount: 3,
    origin: "created",
  },
  {
    id: "legacy_marketing",
    name: "Marketing Attribution",
    description: "Adopted from the existing estate — spec partially recovered",
    criticality: "medium",
    owner: { team: "growth-data" },
    target: { warehouse: "Snowflake", orchestrator: "Airflow" },
    schedule: { cron: "30 4 * * *", humanized: "Daily at 04:30 UTC" },
    lastRun: { state: "success", startedAt: ago(288), durationSeconds: 903 },
    modelCount: 27,
    consumerCount: 6,
    origin: "adopted",
  },
]

export const incidents: Incident[] = [
  {
    id: "inc_1829",
    number: 1829,
    title: "customer_360 failed — upstream type change in Salesforce",
    severity: "high",
    status: "awaiting_approval",
    pipelineId: "customer_360",
    pipelineName: "Customer 360",
    detectedAt: ago(41),
    failedNode: "dim_customer",
    hypotheses: [
      {
        id: "hyp_schema_drift",
        title: "Upstream schema change in salesforce.account",
        confidence: 0.94,
        evidence: [
          {
            id: "ev_1",
            summary: "salesforce.account.id changed from NUMBER to VARCHAR",
            detail:
              "Column type observed as NUMBER(18,0) at 05:31 UTC and VARCHAR(18) at 05:58 UTC. " +
              "The change landed 27 minutes before the first failed run.",
            source: "Snowflake INFORMATION_SCHEMA.COLUMNS snapshot diff",
            observedAt: ago(68),
            supports: true,
          },
          {
            id: "ev_2",
            summary: "Join predicate compares VARCHAR to NUMBER",
            detail:
              "dim_customer joins stg_users.account_id (NUMBER) to stg_accounts.customer_id, " +
              "which now resolves to VARCHAR. Snowflake raises a type mismatch rather than coercing.",
            source: "Compiled SQL for dim_customer, run 2026-09-05T06:00Z",
            observedAt: ago(41),
            supports: true,
          },
          {
            id: "ev_3",
            summary: "Airflow task failed with SQL compilation error",
            detail:
              "Task dim_customer raised: 'Numeric value \\'ACC-00193\\' is not recognized'. " +
              "The literal is a Salesforce account id in the new string format.",
            source: "Airflow task log, dag_id=customer_360, try 1 of 2",
            observedAt: ago(41),
            supports: true,
          },
        ],
      },
      {
        id: "hyp_deploy",
        title: "Recent deployment to the transformation layer",
        confidence: 0.08,
        evidence: [
          {
            id: "ev_4",
            summary: "No commits touching customer_360 in the failure window",
            detail:
              "Most recent commit affecting any model in this pipeline's lineage is 6 days old " +
              "(a4f21c9, 'chore: bump dbt to 1.8.4'). No deployment correlates with the failure.",
            source: "GitHub — acme/analytics, main branch history",
            observedAt: ago(41),
            supports: false,
          },
        ],
      },
      {
        id: "hyp_resource",
        title: "Warehouse resource exhaustion",
        confidence: 0.02,
        evidence: [
          {
            id: "ev_5",
            summary: "Warehouse had spare capacity throughout the run",
            detail:
              "TRANSFORM_WH peaked at 34% of allocated credits during the window, with no " +
              "queued queries. The task failed in 3.4s, far short of any timeout.",
            source: "Snowflake WAREHOUSE_METERING_HISTORY",
            observedAt: ago(41),
            supports: false,
          },
        ],
      },
    ],
    impact: [
      { id: "dim_customer", name: "dim_customer", kind: "model", criticality: "high" },
      { id: "exec_dashboard", name: "Executive Overview", kind: "dashboard", criticality: "high" },
      { id: "crm_sync", name: "CRM enrichment sync", kind: "export", criticality: "medium" },
    ],
    remediation: {
      id: "rem_1829",
      summary: "Cast account_id to VARCHAR in stg_users before the join",
      rationale:
        "The upstream type change is authoritative and will not be reverted — Salesforce " +
        "migrated to string ids across the org. Casting on our side in the staging layer " +
        "keeps the fix in one place and leaves dim_customer untouched.",
      diff: `--- a/models/staging/stg_users.sql
+++ b/models/staging/stg_users.sql
@@ -1,5 +1,5 @@
 SELECT
     id AS user_id,
-    account_id
+    CAST(account_id AS VARCHAR) AS account_id
 FROM {{ ref('app_users') }}`,
      requiredLevel: 3,
      validation: {
        ran: true,
        testsPassed: 43,
        testsTotal: 43,
        sandbox: "ANALYTICS_SANDBOX.nexus_inc_1829",
      },
    },
  },
  {
    id: "inc_1828",
    number: 1828,
    title: "product_events — source freshness breached on kafka.page_views",
    severity: "medium",
    status: "investigating",
    pipelineId: "product_events",
    pipelineName: "Product Events",
    detectedAt: ago(96),
    failedNode: "stg_page_views",
    hypotheses: [
      {
        id: "hyp_stale",
        title: "Upstream connector lag",
        confidence: 0.71,
        evidence: [
          {
            id: "ev_6",
            summary: "No new partitions for 3h 12m against a 1h threshold",
            detail:
              "Latest partition timestamp is 05:48 UTC. The freshness policy warns at 1h and " +
              "errors at 3h; the error threshold was crossed at 08:48 UTC.",
            source: "Snowflake — max(_ingested_at) on raw.page_views",
            observedAt: ago(24),
            supports: true,
          },
        ],
      },
    ],
    impact: [
      { id: "stg_page_views", name: "stg_page_views", kind: "model", criticality: "medium" },
      { id: "growth_dash", name: "Growth Weekly", kind: "dashboard", criticality: "low" },
    ],
  },
]

export function getIncident(id: string): Incident | undefined {
  return incidents.find((i) => i.id === id)
}

export function getPipeline(id: string): Pipeline | undefined {
  return pipelines.find((p) => p.id === id)
}

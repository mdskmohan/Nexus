# Build plan

Nexus is a data-native Agent Studio. Developers connect their warehouses, Nexus learns the business context
from them, and developers build multi-agent data applications on a visual canvas. People approve the steps
that matter, and every number an agent reports is checked against the query result it came from.

This plan is the order we build in and what "done" means for each step. The architecture is in
[architecture.md](architecture.md); each decision has a record in [adr/](adr/).

## Who it is for

Enterprises whose data lives in more than one warehouse (Snowflake and Databricks first), that already have
developers building AI applications on that data. The platform is horizontal. Industry packs (ontologies,
metric libraries, agent templates and guardrail rules for one industry) come later, and the platform loads
them as data so nothing in the core changes for them ([ADR-010](adr/ADR-010-industry-packs-as-data.md)).

## Milestones

| | Milestone | Done when |
|---|---|---|
| **M0** | **Foundation** | Workspaces, sign-in, roles, bring-your-own AI models with encrypted keys, durable runs (queue, pause for a person, stop, crash recovery), append-only audit trail. Tests pass against a real Postgres. Web app shell with sign-in and workspace settings. |
| **M1** | **Connect + knowledge graph** | Snowflake and Databricks connections; schemas, lineage, semantic and metric views and query history collected; everything lands in the knowledge graph (Apache AGE) as proposals; a steward reviews and approves metrics, joins and joins across warehouses. |
| **M2** | **Agent Studio v1** | Agent spec (JSON Schema) and runtime; canvas (React Flow) with Start, Knowledge, SQL, Combine, AI step, Branch, Approval and Output nodes; live test run showing each step. A cross-warehouse revenue agent is built and run on the canvas. |
| **M3** | **Human-in-the-loop and trust** | Approval policies by role and threshold, approvals inbox, pause and resume across restarts, clarification questions, number verification, every run and decision recorded in the context graph. |
| **M4** | **Multi-agent + evals** | Planner, Sub-agent, Loop and Parallel nodes; evals per agent; versions, publish and rollback. |
| **M5** | **Business-user apps** | A published agent becomes a chat and report app for business users, under the same permissions and approvals. |
| **M6** | **Proof** | A cross-warehouse demo and a benchmark (time to build, correct-answer rate) against the same app built with an agent framework and each warehouse's own tools. |
| Later | | SDK (Python, then TypeScript) that writes the same agent spec; dashboards; more connectors; SSO and SCIM; billing; deployment in the customer's own cloud; industry packs. |

## M0 in detail

What is ported from the earlier product in this repository (tag `archive/legal-v0`), and what changes:

| Piece | From legal-v0 | Change |
|---|---|---|
| Tenant isolation | Postgres row-level security keyed on a transaction setting | "Firm" becomes **workspace** |
| Sign-up, sign-in, team | Cookie session, CSRF header, argon2 passwords | Roles become **admin, steward, developer, analyst, viewer**, checked as permissions, not a ladder |
| AI models | Adapters for Claude, GPT, Gemini and OpenAI-compatible endpoints; keys encrypted per tenant | Unchanged apart from naming |
| Job queue | Postgres queue with `FOR UPDATE SKIP LOCKED`, retries, dead-worker recovery | Unchanged |
| Runs | Run record, live step log, cost metering, stop, interrupted-run recovery | New states for human-in-the-loop: `waiting` (paused for a person) and `succeeded`; run kinds are registered by the runtime instead of hard-coded |
| Audit | Append-only table, enforced by a trigger and grants | Unchanged |
| Web | Next.js shell, sign-in, settings, AI models | Navigation for the new product; legal screens removed |

Not ported: documents, matters, playbooks, citations, legal agents and benchmarks.

## Risks we are watching

- **Permission passthrough** (queries run with the user's own warehouse permissions) is fiddly in both
  warehouses. It is proven in M1, before anything depends on it.
- **Suggested joins across warehouses can be wrong.** That is why a steward must approve them.
- **Apache AGE is less mature than Neo4j.** All graph access goes through one interface, so the store can be
  replaced ([ADR-003](adr/ADR-003-knowledge-graph-in-apache-age.md)).
- **Real Snowflake and Databricks accounts** (trials are enough) are needed by M2 at the latest. Until then,
  Postgres and DuckDB fixtures sit behind the same connector interface.

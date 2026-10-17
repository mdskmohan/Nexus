# Nexus

**Agent Studio for data teams: build agents on your warehouses, with people in the loop and every number
checked.**

Nexus connects to an enterprise's warehouses (Snowflake and Databricks first), learns the business context
from them into a knowledge graph that a data steward approves, and lets developers build multi-agent data
applications on a visual canvas. Runs pause for a person wherever an approval or an answer is needed, and
every number an agent reports must trace back to the query result it came from.

> Earlier products in this repository are preserved at the git tags `archive/legal-v0` (an AI legal
> assistant) and `archive/data-pipelines-v0` (a data-pipeline control plane).

## Status

**M0, the foundation, is built:** workspaces with database-enforced isolation, sign-in, roles as permissions
(admin, steward, developer, analyst, viewer), bring-your-own AI models (Claude, GPT, Gemini,
OpenAI-compatible and on-premises) with encrypted keys, durable runs that pause for a person and resume
without repeating work, stopping runs, recovery after a crash, and an append-only audit trail. A web app with
sign-in, an approvals inbox and workspace settings. 30 automated tests pass against a real Postgres.

**M1, connections and the knowledge graph, is mostly built:** connections to the ten platforms enterprises
use most ([connectors](docs/connectors.md)), with encrypted credentials; MySQL, SQL Server, Oracle and
Postgres proven against real servers; tables, columns and declared keys read into the graph as proposals;
join suggestions checked against real data, including joins across warehouses; metrics and entities; steward
review with graph versions; join paths in Apache AGE. 53 tests pass. Still open: semantic views, lineage,
query history, per-user warehouse permissions, and testing Snowflake, Databricks, BigQuery, Redshift,
SAP HANA and Teradata against real accounts. See the [build plan](docs/build-plan.md).

## Quick start

Requirements: Docker, Python 3.12 with [uv](https://docs.astral.sh/uv/), Node.js 20.9+.

```bash
cp .env.example .env          # set NEXUS_JWT_SECRET and NEXUS_SECRET_KEY
make dev                      # database, API, worker and web app
```

Open http://localhost:3100, create a workspace, and connect an AI model in Workspace settings. To try the
knowledge graph without a warehouse, add two demo warehouses to your workspace:

```bash
cd services/api && uv run nexus-seed-demo --email you@example.com
```

```bash
make test                     # backend tests against a real Postgres
```

## Documentation

- [Build plan](docs/build-plan.md): milestones and what "done" means for each
- [Architecture](docs/architecture.md): how the system fits together
- [Decision records](docs/adr/README.md): each decision, why, and what it costs

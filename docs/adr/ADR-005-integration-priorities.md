# ADR-005: Integration priorities

- **Status:** Accepted
- **Date:** 2026-09-05

## Context

The data engineering landscape spans roughly 26 categories and well over a hundred
tools. Nexus claims to operate a customer's whole estate, which creates an obvious
failure mode: spreading thin across many shallow connectors, none of which is good
enough to diagnose anything, and shipping nothing demonstrable for months.

Integrations are also not equal in cost. dbt's manifest is a file on disk. Snowflake
needs credentials and a security review. Kafka needs a different execution model
entirely. Ordering them by customer demand alone would be a mistake.

## Decision

Tier every integration P0, P1 or P2 against five criteria, in this order:

1. **Does the create → deploy → operate loop close without it?** If V1 cannot
   function, it is P0 regardless of effort.
2. **Leverage per unit of integration cost.** A file on disk that yields the whole
   model DAG outranks an API that yields one signal.
3. **Partnership alignment.** Snowflake and Databricks are the intended first
   channel (ADR-002), so their integrations carry weight beyond their technical merit.
4. **Does it produce evidence the diagnosis engine can cite?** Run state, schema
   history and deployment history are what root-cause analysis is built from.
5. **Does it fit the current IR?** Anything requiring an IR change is deferred until
   the batch model is proven.

### P0 — V1 does not exist without these

| Integration | Why it is P0 |
| --- | --- |
| **dbt** | The model DAG, SQL, tests and freshness — no credentials required. Done. |
| **Airflow** | Schedule, run state and task logs. dbt cannot tell us *when* anything ran or what happened. |
| **Snowflake** | The compile target and the source of schema history and query history. Partnership priority. |
| **GitHub** | Generated code has to live somewhere, and remediation is delivered as a pull request (ADR-003, level 2). |
| **PostgreSQL** | The reference use case's operational source, and the local stand-in warehouse that makes the whole stack testable without credentials. |
| **OpenLineage** | Promoted from P1 — see the amendment below. Runtime lineage across every execution engine through one implementation, and the data behind the lineage view engineers actually use. |

Six integrations close the loop for one use case on one stack. That is the whole of V1.

### P1 — needed for the second and third customer

Broadens coverage without changing the architecture. Each is a new adapter behind an
existing interface, not a new concept.

Databricks (second warehouse target and second partnership), BigQuery, Fivetran and
Airbyte (managed ingestion — the end-to-end creation claim is weak without it),
GitHub Actions and GitLab CI (the deployment path), Dagster and Prefect (orchestrator
alternatives), Great Expectations and Soda (quality signals beyond dbt tests),
Terraform (infrastructure a pipeline depends on), secrets managers (Vault, AWS Secrets
Manager), and the BI tools — Looker, Power BI, Tableau — which extend impact analysis
past the exposures dbt happens to declare.

**Secrets management is P1 only while autonomy stays at level 2.** Read-only access
plus pull-request delivery needs no write credentials. The first customer who wants
level 3 makes it P0 immediately.

### P2 — deferred, and some deliberately

Streaming (Kafka, Confluent, Kinesis, Pulsar) and distributed processing (Spark,
Flink, Beam, Ray) are deferred on criterion 5: `PipelineSpec` currently assumes batch —
a cron schedule and a materialization — and streaming is a genuinely different
execution model that would force IR v2. Deferred until the batch model is proven, not
because demand is low.

NoSQL stores (MongoDB, Cassandra, DynamoDB, Redis), enterprise databases (Oracle, SQL
Server), reverse ETL (Hightouch, Census), API integration platforms (MuleSoft, Boomi,
Workato), ML platforms (MLflow, SageMaker, Vertex AI) and infrastructure monitoring
(Datadog, Grafana, Prometheus) are ordinary P2: real, wanted eventually, not on the
critical path. Most will arrive attached to a specific deal.

Three categories are P2 for strategic rather than technical reasons, and the
distinction matters:

- **Data observability** (Monte Carlo, Bigeye, Acceldata) — these are competitors, not
  integrations. Reading their alerts as an evidence source is defensible; building
  deep interoperability with the category we intend to displace is a strategy
  decision, not a backlog item.
- **Catalogs** (Atlan, Alation, DataHub, OpenMetadata) — the environment graph is a
  competing asset. Consuming a customer's existing catalog as a seed is useful;
  positioning Nexus as a catalog client is not.
- **Governance** (Collibra, Purview) — adjacent, enterprise-driven, and better
  approached as a partnership than a connector.

Containers (Docker, Kubernetes) and API clients (Postman) are not integrations at all;
they are how workloads run and how humans test. They are excluded from the catalogue.

## Consequences

**Good.** Five P0 integrations is a scope a small team can finish and prove. The tiers
give a defensible answer to "do you support X" — yes, no, or not yet and here is what
would move it.

**Costly.** A prospect whose estate centres on a P2 tool is not a V1 customer, and we
should say so rather than promise a connector. Heterogeneous estates are the thesis
(ADR-002), but heterogeneous does not mean unbounded.

**Watch for.** Tiering is a snapshot of strategy, not a permanent ranking. A
partnership, a funded design partner, or the first level-3 customer each re-rank this
list. `docs/integrations.md` tracks live status; this ADR records the reasoning.

## Alternatives considered

- **Order by customer demand.** Would have put streaming and Databricks first and
  broken the IR before the batch model was proven.
- **Build a generic plugin SDK and let others fill the catalogue.** Premature. We do
  not yet know what a connector needs to expose, and the interface would be wrong.

---

## Amendment — 2026-09-05: OpenLineage promoted to P0

OpenLineage moves from P1 to P0. Two reasons, neither of which was weighted correctly
in the original tiering.

**It is a user-facing feature, not just a graph-population mechanism.** Lineage is how a
data engineer answers "what broke, where, and what does it feed" — the question the
product exists to answer. Treating it as internal plumbing to be added later would have
shipped a V1 whose headline screen had no data behind it.

**Creation-first makes it nearly free for our own pipelines.** Because Nexus generates
and deploys the orchestration config (ADR-002), we can wire the OpenLineage listener in
at deploy time. Every pipeline Nexus builds emits lineage automatically, with no
customer action and no reconstruction after the fact.

The cost, recorded honestly: **OpenLineage is push-based.** Jobs emit events to a
collector, so unlike dbt's manifest it is not zero-touch for pipelines we did not
build. Adopting an existing estate requires the customer to enable the integration in
their own Airflow or Spark — a real ask during a security review. The asymmetry is
worth naming: lineage is automatic for what we create and negotiated for what we adopt.

This also changes the criterion-2 reading. Leverage per unit of cost is exceptional
*because it is a standard rather than a vendor*: one implementation yields lineage from
Airflow, Spark, dbt, Dagster and Flink at once, so it is the single highest-return
integration in the catalogue after dbt.

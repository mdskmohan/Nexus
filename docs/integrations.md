# Integration catalogue

Live status of every integration Nexus targets. The **reasoning** behind the tiers is
in [ADR-005](adr/ADR-005-integration-priorities.md); this file tracks **state** and is
updated as connectors land.

**Tiers.** P0 — V1 does not exist without it. P1 — needed for the second and third
customer; a new adapter behind an existing interface. P2 — deferred; see the ADR for
which are deferred technically and which strategically.

**Status.** `done` · `in progress` · `planned` · `not started` · `deliberate no`

---

## P0 — the V1 loop

| Layer | Tool | Status | What Nexus reads or writes |
| --- | --- | --- | --- |
| Transformation | **dbt** | `done` | Model DAG, authored SQL, tests, declared freshness, exposures, owners |
| Orchestration | **Airflow** | `done` | DAG schedule, run state, task instances, task logs |
| Warehouse | **Snowflake** | `not started` | DDL emission, `INFORMATION_SCHEMA` snapshots, query history, warehouse metering |
| Version control | **GitHub** | `not started` | Commit and deploy history, PR creation for remediation |
| Database | **PostgreSQL** | `done` | Schema snapshots and drift detection; local stand-in warehouse for tests |

Five integrations close create → deploy → operate for one use case on one stack.

---

## P1 — breadth for customers two and three

| Layer | Tools | Status | Note |
| --- | --- | --- | --- |
| Lineage | **OpenLineage**, Marquez | `planned` | **Pull forward.** A standard, not a vendor — one implementation yields lineage from Airflow, Spark, dbt, Dagster and Flink. Closest thing to P0 leverage in this tier. |
| Lakehouse | Databricks | `not started` | Second warehouse target and second partnership |
| Warehouse | BigQuery, Redshift, Synapse | `not started` | Third-party compile targets |
| ETL / ELT | Fivetran, Airbyte | `not started` | Managed ingestion; the end-to-end creation claim is thin without it |
| CI/CD | GitHub Actions, GitLab CI, Jenkins | `not started` | The deployment path for generated code |
| Orchestration | Dagster, Prefect, Mage | `not started` | Alternatives behind the same orchestrator interface |
| Data quality | Great Expectations, Soda | `not started` | Quality signals beyond dbt tests |
| IaC | Terraform, Pulumi, CloudFormation | `not started` | Infrastructure a pipeline depends on |
| Secrets | Vault, AWS Secrets Manager | `not started` | P1 only while autonomy stays at level 2 — becomes P0 the day a customer wants level 3 |
| BI / Analytics | Looker, Power BI, Tableau, Qlik | `not started` | Extends impact analysis past the exposures dbt happens to declare |
| Object storage | S3, Azure Blob, GCS | `not started` | Lake sources and staging |
| Cloud | AWS, Azure, GCP | `not started` | Identity, networking and compute for deployment |

---

## P2 — deferred

### Deferred on architecture

| Layer | Tools | Why |
| --- | --- | --- |
| Streaming | Kafka, Confluent, Kinesis, Pulsar | `PipelineSpec` assumes batch — a cron schedule and a materialization. Streaming is a different execution model and forces IR v2. Deferred until the batch model is proven, **not** for lack of demand. |
| Distributed processing | Spark, Flink, Beam, Ray | Same reason. Arrives with Databricks-native pipelines. |

### Deferred on strategy

| Layer | Tools | Position |
| --- | --- | --- |
| Observability | Monte Carlo, Bigeye, Acceldata | **Competitors, not integrations.** Reading their alerts as an evidence source is defensible; deep interoperability with the category we intend to displace is a strategy decision, not a backlog item. |
| Catalog | Atlan, Alation, DataHub, OpenMetadata | The environment graph is a competing asset. Consuming a customer's catalog as a *seed* is useful; positioning Nexus as a catalog client is not. |
| Governance | Collibra, Informatica, Microsoft Purview | Adjacent and enterprise-driven. Better approached as a partnership than a connector. |

### Ordinary P2 — real, wanted, not on the critical path

| Layer | Tools |
| --- | --- |
| NoSQL | MongoDB, Cassandra, DynamoDB, Redis |
| Databases | Oracle, SQL Server, MySQL |
| ETL (legacy) | Informatica, Talend, Matillion |
| Reverse ETL | Hightouch, Census |
| API integration | MuleSoft, Boomi, Workato |
| ML platforms | MLflow, SageMaker, Vertex AI, Azure ML |
| Monitoring | Datadog, Grafana, Prometheus |

Most of these will arrive attached to a specific deal rather than a roadmap slot.

---

## Out of scope

Not integrations, and excluded deliberately:

- **Containers** (Docker, Kubernetes) — how workloads run, not a system Nexus reads
- **API clients** (Postman) — a human's testing tool

---

## Adding a connector

1. Confirm the tier, or amend [ADR-005](adr/ADR-005-integration-priorities.md) if the
   reasoning has changed. Do not quietly promote something.
2. Implement the `Connector` protocol in `services/api/nexus/connectors/`. Connectors
   are read-only and deterministic; anything that *changes* a customer system lives in
   the execution layer behind the policy engine.
3. Emit graph entities with system-namespaced ids. Do not join across systems inside a
   connector — cross-system joins are a separate explicit step.
4. Record what you could not recover in `ConnectorResult.warnings`. A silent gap in the
   graph becomes a diagnosis that cannot explain itself.
5. Test against a **real** artifact from the tool, not a handwritten approximation.
   See `tests/fixtures/dbt/README.md` for how the dbt fixture was produced.
6. Update the status column above in the same PR.

# dbt fixtures

`manifest_v12.json` is a **real** manifest, not a handwritten approximation. It was
produced by running `dbt parse` (dbt-core 1.12.3, dbt-postgres 1.11.0) against a small
project with the shape we care about: two sources with differing freshness declarations,
three models across two layers, generic tests on both a model and a source, and an
exposure.

It is checked in whole, including keys Nexus does not read. That is deliberate — the
parser must tolerate unknown fields, and a trimmed fixture would stop proving it.

To regenerate after a dbt upgrade, rebuild the project described in this file's git
history and re-run `dbt parse`, then update the schema-version assertion in
`tests/test_dbt_connector.py`.

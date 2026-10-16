"""Connections and the knowledge graph.

The system of record for the knowledge graph is `kg_items` (one row per table,
column, join, entity or metric, with its review status) and `kg_versions`.
Both are tenant tables under row-level security.

Approved items are projected into an Apache AGE graph, one graph per
workspace, for traversal (join paths, and later lineage). The app role has no
privilege on any graph schema. It reaches its own workspace's graph only
through `kg_cypher`, a SECURITY DEFINER function that derives the graph name
from the transaction's `app.workspace_id`, the same setting row-level security
uses, so no code path can name another workspace's graph.

Revision ID: 0002
"""

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

TENANT_TABLES = ["connections", "kg_versions", "kg_items"]

SCHEMA = """
CREATE EXTENSION IF NOT EXISTS age;

CREATE TABLE connections (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id     uuid NOT NULL REFERENCES workspaces(id),
    kind             text NOT NULL CHECK (kind IN ('snowflake', 'databricks', 'postgres')),
    label            text NOT NULL,
    -- Settings that are not secret (host, warehouse, database...).
    config           jsonb NOT NULL DEFAULT '{}'::jsonb,
    -- AES-GCM ciphertext of the secret settings as JSON (see nexus/ai/secrets.py); never returned.
    secrets_enc      text,
    last_test_ok     boolean,
    last_test_at     timestamptz,
    last_test_msg    text,
    collect_status   text NOT NULL DEFAULT 'never' CHECK (collect_status IN (
                       'never', 'queued', 'running', 'done', 'failed')),
    collected_at     timestamptz,
    collect_msg      text,
    created_by       uuid REFERENCES users(id),
    created_at       timestamptz NOT NULL DEFAULT now()
);

-- One row per approved change set. Runs record the version they planned against.
CREATE TABLE kg_versions (
    id            bigserial PRIMARY KEY,
    workspace_id  uuid NOT NULL REFERENCES workspaces(id),
    number        integer NOT NULL,
    summary       jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_by    uuid REFERENCES users(id),
    created_at    timestamptz NOT NULL DEFAULT now(),
    UNIQUE (workspace_id, number)
);

-- Everything the knowledge graph knows, with its review status. An item is
-- part of graph version N when approved_in <= N and (deprecated_in IS NULL OR
-- deprecated_in > N), so any past version can be reproduced.
CREATE TABLE kg_items (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id   uuid NOT NULL REFERENCES workspaces(id),
    kind           text NOT NULL CHECK (kind IN ('table', 'column', 'join', 'entity', 'metric')),
    -- Stable identity within the workspace: connection id, then database.schema.table.
    key            text NOT NULL,
    connection_id  uuid REFERENCES connections(id) ON DELETE CASCADE,
    -- The table a column, join (left side) or metric belongs to.
    parent_id      uuid REFERENCES kg_items(id) ON DELETE CASCADE,
    name           text NOT NULL,
    description    text NOT NULL DEFAULT '',
    attrs          jsonb NOT NULL DEFAULT '{}'::jsonb,
    status         text NOT NULL DEFAULT 'proposed' CHECK (status IN (
                     'proposed', 'approved', 'rejected', 'deprecated')),
    -- Where the item came from: read from a warehouse, suggested by Nexus, or added by a person.
    origin         text NOT NULL CHECK (origin IN ('discovered', 'suggested', 'person')),
    proposed_by    uuid REFERENCES users(id),
    reviewed_by    uuid REFERENCES users(id),
    reviewed_at    timestamptz,
    review_note    text,
    approved_in    integer,
    deprecated_in  integer,
    -- Set when a discovered item was not seen in the latest collection.
    missing_since  timestamptz,
    created_at     timestamptz NOT NULL DEFAULT now(),
    updated_at     timestamptz NOT NULL DEFAULT now(),
    UNIQUE (workspace_id, kind, key)
);
CREATE INDEX kg_items_review_idx ON kg_items (workspace_id, status, kind);
CREATE INDEX kg_items_parent_idx ON kg_items (parent_id);

-- The calling transaction's workspace graph. Graph names must be identifiers, so
-- the uuid's hyphens are dropped.
CREATE FUNCTION kg_graph() RETURNS name LANGUAGE sql STABLE AS $$
  SELECT ('kg_' || replace(current_setting('app.workspace_id'), '-', ''))::name
$$;

-- Run one Cypher statement against the calling workspace's graph and return each
-- result row as jsonb (statements RETURN a single map). The query text comes from
-- Nexus code; values are always passed in `params`.
CREATE FUNCTION kg_cypher(q text, params jsonb DEFAULT '{}'::jsonb) RETURNS SETOF jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path = ag_catalog, public AS $$
DECLARE
  g name := kg_graph();
BEGIN
  IF position('$kg$' IN q) > 0 THEN
    RAISE EXCEPTION 'invalid graph query';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM ag_catalog.ag_graph WHERE name = g) THEN
    PERFORM ag_catalog.create_graph(g);
  END IF;
  RETURN QUERY EXECUTE format(
    'SELECT r::text::jsonb FROM ag_catalog.cypher(%L, $kg$%s$kg$, $1) AS (r agtype)', g, q)
    USING params::text::ag_catalog.agtype;
END $$;
REVOKE ALL ON FUNCTION kg_cypher(text, jsonb) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION kg_cypher(text, jsonb) TO nexus_app;
"""


def upgrade() -> None:
    op.execute(SCHEMA)
    for table in TENANT_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY tenant_isolation ON {table} "
            "USING (workspace_id = current_setting('app.workspace_id', true)::uuid) "
            "WITH CHECK (workspace_id = current_setting('app.workspace_id', true)::uuid)"
        )
        op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO nexus_app")
    op.execute("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO nexus_app")


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS kg_cypher(text, jsonb)")
    op.execute("DROP FUNCTION IF EXISTS kg_graph()")
    for table in reversed(TENANT_TABLES):
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")

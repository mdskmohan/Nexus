"""Runs: every time Nexus reads a connection, with its progress, results and log.

A run moves queued → running → succeeded | failed | cancelled. While it runs
it records its phase and progress, counts what it found in `stats`, and writes
log lines that people can follow live. A failed run keeps the reason and a
plain-language hint. At most one run per connection is queued or running.

Revision ID: 0004
"""

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

TENANT_TABLES = ["collect_runs", "collect_run_logs"]

SCHEMA = """
CREATE TABLE collect_runs (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id      uuid NOT NULL REFERENCES workspaces(id),
    connection_id     uuid NOT NULL REFERENCES connections(id) ON DELETE CASCADE,
    trigger           text NOT NULL DEFAULT 'manual' CHECK (trigger IN ('manual', 'retry', 'setup', 'schedule')),
    requested_by      uuid REFERENCES users(id),
    status            text NOT NULL DEFAULT 'queued' CHECK (status IN (
                        'queued', 'running', 'succeeded', 'failed', 'cancelled')),
    phase             text NOT NULL DEFAULT 'queued',
    progress          real NOT NULL DEFAULT 0 CHECK (progress BETWEEN 0 AND 100),
    -- Counts of what the run found: schemas, tables, views, columns, new, removed, keys, joins.
    stats             jsonb NOT NULL DEFAULT '{}'::jsonb,
    error             text,
    error_kind        text,
    cancel_requested  boolean NOT NULL DEFAULT false,
    created_at        timestamptz NOT NULL DEFAULT now(),
    started_at        timestamptz,
    finished_at       timestamptz,
    updated_at        timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX collect_runs_recent_idx ON collect_runs (workspace_id, created_at DESC);
CREATE INDEX collect_runs_connection_idx ON collect_runs (connection_id, created_at DESC);
CREATE UNIQUE INDEX collect_runs_one_active ON collect_runs (connection_id) WHERE status IN ('queued', 'running');

CREATE TABLE collect_run_logs (
    id            bigserial PRIMARY KEY,
    workspace_id  uuid NOT NULL REFERENCES workspaces(id),
    run_id        uuid NOT NULL REFERENCES collect_runs(id) ON DELETE CASCADE,
    at            timestamptz NOT NULL DEFAULT clock_timestamp(),
    level         text NOT NULL CHECK (level IN ('info', 'success', 'warning', 'error')),
    message       text NOT NULL,
    data          jsonb
);
CREATE INDEX collect_run_logs_run_idx ON collect_run_logs (run_id, id);
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
    for table in reversed(TENANT_TABLES):
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")

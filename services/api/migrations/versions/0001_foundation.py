"""Foundation: workspaces, people, AI models, durable runs, requests to people, audit trail, jobs.

Tenant isolation is enforced by Postgres row-level security, keyed on the
transaction-local setting `app.workspace_id`. The app role (nexus_app) is not
the table owner, and every tenant table has FORCE ROW LEVEL SECURITY, so a
query that forgets a `WHERE workspace_id = …` still cannot see another
workspace's rows.

Revision ID: 0001
"""

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

TENANT_TABLES = [
    "workspaces",
    "users",
    "ai_providers",
    "ai_models",
    "runs",
    "run_steps",
    "human_requests",
    "audit_events",
]

SCHEMA = """
CREATE TABLE workspaces (
    id          uuid PRIMARY KEY,
    name        text NOT NULL,
    created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE users (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id   uuid NOT NULL REFERENCES workspaces(id),
    email          text NOT NULL,
    name           text NOT NULL,
    password_hash  text NOT NULL,
    role           text NOT NULL CHECK (role IN ('admin', 'steward', 'developer', 'analyst', 'viewer')),
    disabled       boolean NOT NULL DEFAULT false,
    created_at     timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX users_email_uq ON users (lower(email));
CREATE INDEX users_workspace_idx ON users (workspace_id);

CREATE TABLE ai_providers (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id   uuid NOT NULL REFERENCES workspaces(id),
    kind           text NOT NULL CHECK (kind IN ('anthropic', 'openai', 'google', 'openai_compatible')),
    label          text NOT NULL,
    base_url       text,
    -- AES-GCM ciphertext of the API key (see nexus/ai/secrets.py); never returned by the API.
    api_key_enc    text,
    key_last4      text,
    enabled        boolean NOT NULL DEFAULT true,
    last_test_ok   boolean,
    last_test_at   timestamptz,
    last_test_msg  text,
    created_at     timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE ai_models (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id        uuid NOT NULL REFERENCES workspaces(id),
    provider_id         uuid NOT NULL REFERENCES ai_providers(id) ON DELETE CASCADE,
    model               text NOT NULL,
    label               text NOT NULL,
    -- USD per million tokens, if the workspace wants costs and spending limits in money.
    price_in_per_mtok   numeric(10, 4),
    price_out_per_mtok  numeric(10, 4),
    is_default          boolean NOT NULL DEFAULT false,
    enabled             boolean NOT NULL DEFAULT true,
    created_at          timestamptz NOT NULL DEFAULT now(),
    UNIQUE (provider_id, model)
);
CREATE UNIQUE INDEX ai_models_one_default ON ai_models (workspace_id) WHERE is_default;

-- One execution of an agent. `state` holds the run's saved progress, so a run
-- that pauses for a person (status 'waiting') can resume where it stopped.
CREATE TABLE runs (
    id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id       uuid NOT NULL REFERENCES workspaces(id),
    kind               text NOT NULL,
    status             text NOT NULL DEFAULT 'queued' CHECK (status IN (
                         'queued', 'running', 'waiting', 'succeeded', 'failed', 'cancelled')),
    title              text NOT NULL,
    input              jsonb NOT NULL DEFAULT '{}'::jsonb,
    state              jsonb NOT NULL DEFAULT '{}'::jsonb,
    output             jsonb,
    error              text,
    ai_model_id        uuid REFERENCES ai_models(id) ON DELETE SET NULL,
    model              text,
    provider           text,
    input_tokens       integer NOT NULL DEFAULT 0,
    output_tokens      integer NOT NULL DEFAULT 0,
    cache_read_tokens  integer NOT NULL DEFAULT 0,
    cost_usd           numeric(10, 4) NOT NULL DEFAULT 0,
    created_by         uuid REFERENCES users(id),
    created_at         timestamptz NOT NULL DEFAULT now(),
    started_at         timestamptz,
    finished_at        timestamptz
);
CREATE INDEX runs_workspace_idx ON runs (workspace_id, created_at DESC);

CREATE TABLE run_steps (
    id            bigserial PRIMARY KEY,
    workspace_id  uuid NOT NULL REFERENCES workspaces(id),
    run_id        uuid NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    seq           integer NOT NULL,
    kind          text NOT NULL,
    title         text NOT NULL,
    status        text NOT NULL DEFAULT 'ok' CHECK (status IN ('ok', 'warning', 'blocked', 'error')),
    detail        jsonb NOT NULL DEFAULT '{}'::jsonb,
    duration_ms   integer,
    created_at    timestamptz NOT NULL DEFAULT now(),
    UNIQUE (run_id, seq)
);

-- A run asking a person for something: an approval or an answer. The run waits
-- until the request is decided. `shown` is exactly what the person was shown.
CREATE TABLE human_requests (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id  uuid NOT NULL REFERENCES workspaces(id),
    run_id        uuid NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    key           text NOT NULL,
    kind          text NOT NULL CHECK (kind IN ('approval', 'clarification')),
    title         text NOT NULL,
    shown         jsonb NOT NULL DEFAULT '{}'::jsonb,
    -- Who may decide: anyone whose role has this permission.
    permission    text NOT NULL,
    status        text NOT NULL DEFAULT 'open' CHECK (status IN (
                    'open', 'approved', 'rejected', 'answered', 'cancelled')),
    answer        text,
    note          text,
    decided_by    uuid REFERENCES users(id),
    decided_at    timestamptz,
    created_at    timestamptz NOT NULL DEFAULT now(),
    UNIQUE (run_id, key)
);
CREATE INDEX human_requests_open_idx ON human_requests (workspace_id, created_at) WHERE status = 'open';

-- Append-only record of who did what. The app role cannot update or delete it,
-- and a trigger rejects either even for roles that could.
CREATE TABLE audit_events (
    id            bigserial PRIMARY KEY,
    workspace_id  uuid NOT NULL REFERENCES workspaces(id),
    actor_id      uuid REFERENCES users(id),
    action        text NOT NULL,
    target_type   text NOT NULL,
    target_id     text,
    detail        jsonb NOT NULL DEFAULT '{}'::jsonb,
    at            timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX audit_workspace_idx ON audit_events (workspace_id, at DESC);

CREATE FUNCTION audit_events_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'audit_events is append-only';
END $$;
CREATE TRIGGER audit_events_no_change BEFORE UPDATE OR DELETE ON audit_events
  FOR EACH ROW EXECUTE FUNCTION audit_events_immutable();

-- Background work queue. Claimed with FOR UPDATE SKIP LOCKED by the worker,
-- which runs across workspaces, so this table carries no row-level security.
-- The worker switches into the job's workspace before touching any tenant data.
CREATE TABLE jobs (
    id            bigserial PRIMARY KEY,
    workspace_id  uuid NOT NULL,
    kind          text NOT NULL,
    payload       jsonb NOT NULL,
    status        text NOT NULL DEFAULT 'queued' CHECK (status IN ('queued', 'running', 'done', 'failed')),
    attempts      integer NOT NULL DEFAULT 0,
    max_attempts  integer NOT NULL DEFAULT 3,
    run_after     timestamptz NOT NULL DEFAULT now(),
    locked_at     timestamptz,
    locked_by     text,
    last_error    text,
    created_at    timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX jobs_ready_idx ON jobs (run_after) WHERE status = 'queued';

-- Sign-in has to find a user before it knows their workspace. This is the only
-- path around row-level security, and it returns only what sign-in needs.
CREATE FUNCTION auth_lookup(p_email text)
RETURNS TABLE (id uuid, workspace_id uuid, password_hash text, role text, disabled boolean)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public AS $$
  SELECT id, workspace_id, password_hash, role, disabled FROM users WHERE lower(email) = lower(p_email)
$$;
REVOKE ALL ON FUNCTION auth_lookup(text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION auth_lookup(text) TO nexus_app;
"""


def upgrade() -> None:
    op.execute(SCHEMA)
    for table in TENANT_TABLES:
        key = "id" if table == "workspaces" else "workspace_id"
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY tenant_isolation ON {table} "
            f"USING ({key} = current_setting('app.workspace_id', true)::uuid) "
            f"WITH CHECK ({key} = current_setting('app.workspace_id', true)::uuid)"
        )
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON "
        + ", ".join(TENANT_TABLES + ["jobs"])
        + " TO nexus_app"
    )
    op.execute("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO nexus_app")
    op.execute("REVOKE UPDATE, DELETE ON audit_events FROM nexus_app")


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS auth_lookup(text)")
    for table in ["jobs", *reversed(TENANT_TABLES)]:
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
    op.execute("DROP FUNCTION IF EXISTS audit_events_immutable()")

"""Initial schema: firms, people, matters, documents, AI runs, audit trail, jobs.

Tenant isolation is enforced by Postgres row-level security, keyed on the
transaction-local setting `app.firm_id`. The app role (nexus_app) is not the
table owner, and every tenant table has FORCE ROW LEVEL SECURITY, so a query
that forgets a `WHERE firm_id = …` still cannot see another firm's rows.

Revision ID: 0001
"""

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

TENANT_TABLES = [
    "firms",
    "users",
    "matters",
    "documents",
    "passages",
    "playbooks",
    "runs",
    "run_steps",
    "artifacts",
    "audit_events",
]

SCHEMA = """
CREATE TABLE firms (
    id           uuid PRIMARY KEY,
    name         text NOT NULL,
    preferences  text NOT NULL DEFAULT '',
    created_at   timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE users (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    firm_id        uuid NOT NULL REFERENCES firms(id),
    email          text NOT NULL,
    name           text NOT NULL,
    password_hash  text NOT NULL,
    role           text NOT NULL CHECK (role IN ('admin', 'partner', 'associate', 'paralegal')),
    disabled       boolean NOT NULL DEFAULT false,
    created_at     timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX users_email_uq ON users (lower(email));
CREATE INDEX users_firm_idx ON users (firm_id);

CREATE TABLE matters (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    firm_id      uuid NOT NULL REFERENCES firms(id),
    name         text NOT NULL,
    client_name  text NOT NULL DEFAULT '',
    description  text NOT NULL DEFAULT '',
    status       text NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'closed')),
    created_by   uuid REFERENCES users(id),
    created_at   timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX matters_firm_idx ON matters (firm_id, created_at DESC);

CREATE TABLE documents (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    firm_id       uuid NOT NULL REFERENCES firms(id),
    matter_id     uuid NOT NULL REFERENCES matters(id) ON DELETE CASCADE,
    filename      text NOT NULL,
    content_type  text NOT NULL,
    size_bytes    bigint NOT NULL,
    sha256        text NOT NULL,
    storage_key   text NOT NULL,
    status        text NOT NULL DEFAULT 'queued'
                  CHECK (status IN ('queued', 'processing', 'ready', 'failed')),
    page_count    integer,
    error         text,
    -- Guardrail findings from ingestion (hidden instructions, sensitive numbers).
    flags         jsonb NOT NULL DEFAULT '{}'::jsonb,
    uploaded_by   uuid REFERENCES users(id),
    created_at    timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX documents_matter_idx ON documents (matter_id, created_at);

CREATE TABLE passages (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    firm_id      uuid NOT NULL REFERENCES firms(id),
    matter_id    uuid NOT NULL REFERENCES matters(id) ON DELETE CASCADE,
    document_id  uuid NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    seq          integer NOT NULL,
    page         integer NOT NULL,
    heading      text NOT NULL DEFAULT '',
    text         text NOT NULL,
    tsv          tsvector GENERATED ALWAYS AS (
                   setweight(to_tsvector('english', heading), 'A') ||
                   setweight(to_tsvector('english', text), 'B')
                 ) STORED,
    UNIQUE (document_id, seq)
);
CREATE INDEX passages_tsv_idx ON passages USING gin (tsv);
CREATE INDEX passages_matter_idx ON passages (matter_id);

CREATE TABLE playbooks (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    firm_id       uuid NOT NULL REFERENCES firms(id),
    slug          text NOT NULL,
    name          text NOT NULL,
    description   text NOT NULL DEFAULT '',
    document_type text NOT NULL,
    positions     jsonb NOT NULL,
    is_starter    boolean NOT NULL DEFAULT false,
    -- Who (a qualified lawyer) has reviewed and approved this playbook, if anyone.
    validated_by  text,
    validated_at  timestamptz,
    updated_at    timestamptz NOT NULL DEFAULT now(),
    UNIQUE (firm_id, slug)
);

CREATE TABLE runs (
    id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    firm_id            uuid NOT NULL REFERENCES firms(id),
    matter_id          uuid NOT NULL REFERENCES matters(id) ON DELETE CASCADE,
    kind               text NOT NULL CHECK (kind IN ('ask', 'review')),
    status             text NOT NULL DEFAULT 'queued' CHECK (status IN (
                         'queued', 'running', 'needs_review', 'approved', 'rejected', 'failed')),
    title              text NOT NULL,
    input              jsonb NOT NULL,
    output             jsonb,
    guardrails         jsonb NOT NULL DEFAULT '{}'::jsonb,
    error              text,
    model              text,
    input_tokens       integer NOT NULL DEFAULT 0,
    output_tokens      integer NOT NULL DEFAULT 0,
    cache_read_tokens  integer NOT NULL DEFAULT 0,
    cost_usd           numeric(10, 4) NOT NULL DEFAULT 0,
    created_by         uuid REFERENCES users(id),
    reviewed_by        uuid REFERENCES users(id),
    reviewed_at        timestamptz,
    review_note        text,
    created_at         timestamptz NOT NULL DEFAULT now(),
    started_at         timestamptz,
    finished_at        timestamptz
);
CREATE INDEX runs_matter_idx ON runs (matter_id, created_at DESC);
CREATE INDEX runs_firm_idx ON runs (firm_id, created_at DESC);

CREATE TABLE run_steps (
    id           bigserial PRIMARY KEY,
    firm_id      uuid NOT NULL REFERENCES firms(id),
    run_id       uuid NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    seq          integer NOT NULL,
    kind         text NOT NULL,
    title        text NOT NULL,
    status       text NOT NULL DEFAULT 'ok' CHECK (status IN ('ok', 'warning', 'blocked', 'error')),
    detail       jsonb NOT NULL DEFAULT '{}'::jsonb,
    duration_ms  integer,
    created_at   timestamptz NOT NULL DEFAULT now(),
    UNIQUE (run_id, seq)
);

CREATE TABLE artifacts (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    firm_id       uuid NOT NULL REFERENCES firms(id),
    run_id        uuid NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    filename      text NOT NULL,
    content_type  text NOT NULL,
    storage_key   text NOT NULL,
    created_at    timestamptz NOT NULL DEFAULT now()
);

-- Append-only record of who did what. The app role cannot update or delete it,
-- and a trigger rejects either even for roles that could.
CREATE TABLE audit_events (
    id           bigserial PRIMARY KEY,
    firm_id      uuid NOT NULL REFERENCES firms(id),
    actor_id     uuid REFERENCES users(id),
    action       text NOT NULL,
    target_type  text NOT NULL,
    target_id    text,
    detail       jsonb NOT NULL DEFAULT '{}'::jsonb,
    at           timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX audit_firm_idx ON audit_events (firm_id, at DESC);

CREATE FUNCTION audit_events_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'audit_events is append-only';
END $$;
CREATE TRIGGER audit_events_no_change BEFORE UPDATE OR DELETE ON audit_events
  FOR EACH ROW EXECUTE FUNCTION audit_events_immutable();

-- Background work queue. Claimed with FOR UPDATE SKIP LOCKED by the worker,
-- which runs across firms, so this table carries no row-level security. The
-- worker switches into the job's firm before touching any tenant data.
CREATE TABLE jobs (
    id            bigserial PRIMARY KEY,
    firm_id       uuid NOT NULL,
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

-- Login has to find a user before it knows their firm. This is the only
-- path around row-level security, and it returns only what login needs.
CREATE FUNCTION auth_lookup(p_email text)
RETURNS TABLE (id uuid, firm_id uuid, password_hash text, role text, disabled boolean)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public AS $$
  SELECT id, firm_id, password_hash, role, disabled FROM users WHERE lower(email) = lower(p_email)
$$;
REVOKE ALL ON FUNCTION auth_lookup(text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION auth_lookup(text) TO nexus_app;
"""


def upgrade() -> None:
    op.execute(SCHEMA)
    for table in TENANT_TABLES:
        key = "id" if table == "firms" else "firm_id"
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY tenant_isolation ON {table} "
            f"USING ({key} = current_setting('app.firm_id', true)::uuid) "
            f"WITH CHECK ({key} = current_setting('app.firm_id', true)::uuid)"
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

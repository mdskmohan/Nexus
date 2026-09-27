"""Bring-your-own AI: each firm's model providers (with encrypted keys) and models.

Revision ID: 0003
"""

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

SCHEMA = """
CREATE TABLE ai_providers (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    firm_id        uuid NOT NULL REFERENCES firms(id),
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
    firm_id             uuid NOT NULL REFERENCES firms(id),
    provider_id         uuid NOT NULL REFERENCES ai_providers(id) ON DELETE CASCADE,
    model               text NOT NULL,
    label               text NOT NULL,
    -- USD per million tokens, if the firm wants costs and spending limits in money.
    price_in_per_mtok   numeric(10, 4),
    price_out_per_mtok  numeric(10, 4),
    is_default          boolean NOT NULL DEFAULT false,
    enabled             boolean NOT NULL DEFAULT true,
    created_at          timestamptz NOT NULL DEFAULT now(),
    UNIQUE (provider_id, model)
);
CREATE UNIQUE INDEX ai_models_one_default ON ai_models (firm_id) WHERE is_default;

ALTER TABLE runs ADD COLUMN ai_model_id uuid REFERENCES ai_models(id) ON DELETE SET NULL;
ALTER TABLE runs ADD COLUMN provider text;
"""


def upgrade() -> None:
    op.execute(SCHEMA)
    for table in ("ai_providers", "ai_models"):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY tenant_isolation ON {table} "
            "USING (firm_id = current_setting('app.firm_id', true)::uuid) "
            "WITH CHECK (firm_id = current_setting('app.firm_id', true)::uuid)"
        )
        op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO nexus_app")


def downgrade() -> None:
    op.execute("ALTER TABLE runs DROP COLUMN IF EXISTS provider")
    op.execute("ALTER TABLE runs DROP COLUMN IF EXISTS ai_model_id")
    op.execute("DROP TABLE IF EXISTS ai_models")
    op.execute("DROP TABLE IF EXISTS ai_providers")

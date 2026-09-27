"""Allow legal-notice runs.

Revision ID: 0005
"""

from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE runs DROP CONSTRAINT runs_kind_check")
    op.execute("ALTER TABLE runs ADD CONSTRAINT runs_kind_check CHECK (kind IN ('ask', 'review', 'draft', 'notice'))")


def downgrade() -> None:
    op.execute("DELETE FROM runs WHERE kind = 'notice'")
    op.execute("ALTER TABLE runs DROP CONSTRAINT runs_kind_check")
    op.execute("ALTER TABLE runs ADD CONSTRAINT runs_kind_check CHECK (kind IN ('ask', 'review', 'draft'))")

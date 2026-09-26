"""Allow drafting runs.

Revision ID: 0002
"""

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE runs DROP CONSTRAINT runs_kind_check")
    op.execute("ALTER TABLE runs ADD CONSTRAINT runs_kind_check CHECK (kind IN ('ask', 'review', 'draft'))")


def downgrade() -> None:
    op.execute("DELETE FROM runs WHERE kind = 'draft'")
    op.execute("ALTER TABLE runs DROP CONSTRAINT runs_kind_check")
    op.execute("ALTER TABLE runs ADD CONSTRAINT runs_kind_check CHECK (kind IN ('ask', 'review'))")

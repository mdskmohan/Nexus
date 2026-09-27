"""Let people stop a running task.

Revision ID: 0004
"""

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE runs DROP CONSTRAINT runs_status_check")
    op.execute("""ALTER TABLE runs ADD CONSTRAINT runs_status_check CHECK (status IN (
                  'queued', 'running', 'needs_review', 'approved', 'rejected', 'failed', 'cancelled'))""")


def downgrade() -> None:
    op.execute("UPDATE runs SET status = 'failed' WHERE status = 'cancelled'")
    op.execute("ALTER TABLE runs DROP CONSTRAINT runs_status_check")
    op.execute("""ALTER TABLE runs ADD CONSTRAINT runs_status_check CHECK (status IN (
                  'queued', 'running', 'needs_review', 'approved', 'rejected', 'failed'))""")

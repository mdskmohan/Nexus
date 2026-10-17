"""Seven more kinds of connection: SQL Server, Oracle, BigQuery, Redshift, SAP HANA, Teradata, MySQL.

Revision ID: 0003
"""

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

KINDS = ("snowflake", "databricks", "sqlserver", "oracle", "bigquery", "redshift", "saphana", "postgres",
         "teradata", "mysql")


def upgrade() -> None:
    op.execute("ALTER TABLE connections DROP CONSTRAINT connections_kind_check")
    op.execute(f"ALTER TABLE connections ADD CONSTRAINT connections_kind_check CHECK (kind IN {KINDS!r})")


def downgrade() -> None:
    op.execute("ALTER TABLE connections DROP CONSTRAINT connections_kind_check")
    op.execute("ALTER TABLE connections ADD CONSTRAINT connections_kind_check "
               "CHECK (kind IN ('snowflake', 'databricks', 'postgres'))")

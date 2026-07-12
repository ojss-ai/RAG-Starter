"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-07-12

One concern: the complete initial schema. Table shapes come from Base.metadata (models ==
schema at revision zero by definition; later migrations use explicit ops). The PG-only
pieces — generated tsvector column on chunks + GIN index — are added with dialect-guarded
DDL and dropped symmetrically on downgrade.
"""
from alembic import op

from app.db import Base
from app import models  # noqa: F401

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(bind)
    if bind.dialect.name == "postgresql":
        op.execute(
            "ALTER TABLE chunks ADD COLUMN ts tsvector "
            "GENERATED ALWAYS AS (to_tsvector('english', text)) STORED"
        )
        op.execute("CREATE INDEX ix_chunks_ts ON chunks USING GIN (ts)")


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("DROP INDEX IF EXISTS ix_chunks_ts")
        op.execute("ALTER TABLE chunks DROP COLUMN IF EXISTS ts")
    Base.metadata.drop_all(bind)

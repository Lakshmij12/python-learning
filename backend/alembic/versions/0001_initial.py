"""initial schema

Bootstraps the database:
  1. enables the pgvector extension (required before creating vector columns),
  2. creates every table from the application metadata (single source of truth),
  3. adds an HNSW index on ``embeddings.vector`` for cosine ANN search.

Subsequent schema changes should be produced with
``alembic revision --autogenerate -m "<change>"``.

Revision ID: 0001_initial
Revises:
Create Date: 2026-07-27
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

from app.models import Base

# revision identifiers, used by Alembic.
revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    if is_postgres:
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # Create all tables defined on the application metadata.
    Base.metadata.create_all(bind=bind)

    if is_postgres:
        # Approximate-nearest-neighbour index for semantic search (cosine).
        op.execute(
            "CREATE INDEX IF NOT EXISTS ix_embeddings_vector_hnsw "
            "ON embeddings USING hnsw (vector vector_cosine_ops)"
        )


def downgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    if is_postgres:
        op.execute("DROP INDEX IF EXISTS ix_embeddings_vector_hnsw")

    Base.metadata.drop_all(bind=bind)

    if is_postgres:
        op.execute("DROP EXTENSION IF EXISTS vector")

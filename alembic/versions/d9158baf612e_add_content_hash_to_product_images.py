"""add content hash to product images

Revision ID: d9158baf612e
Revises: 52f63f62a619
Create Date: 2026-08-28
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d9158baf612e"
down_revision: str | None = "52f63f62a619"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "product_images",
        sa.Column("content_hash", sa.String(length=64), nullable=True),
    )
    op.create_unique_constraint(
        "uq_product_images_product_id_content_hash",
        "product_images",
        ["product_id", "content_hash"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_product_images_product_id_content_hash",
        "product_images",
        type_="unique",
    )
    op.drop_column("product_images", "content_hash")

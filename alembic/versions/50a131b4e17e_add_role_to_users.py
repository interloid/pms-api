"""Add role to users

Revision ID: 50a131b4e17e
Revises: d9158baf612e
Create Date: 2026-08-31 12:01:56.619193
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "50a131b4e17e"
down_revision: Union[str, None] = "d9158baf612e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


user_role_enum = postgresql.ENUM(
    "viewer",
    "editor",
    "admin",
    name="user_role",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()

    # Create the PostgreSQL enum type
    postgresql.ENUM(
        "viewer",
        "editor",
        "admin",
        name="user_role",
    ).create(
        bind,
        checkfirst=True,
    )

    # Add the role column
    op.add_column(
        "users",
        sa.Column(
            "role",
            user_role_enum,
            nullable=False,
            server_default=sa.text("'viewer'::user_role"),
        ),
    )

    op.create_index(
        op.f("ix_users_role"),
        "users",
        ["role"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_users_role"),
        table_name="users",
    )

    op.drop_column(
        "users",
        "role",
    )

    user_role_enum.drop(
        op.get_bind(),
        checkfirst=True,
    )
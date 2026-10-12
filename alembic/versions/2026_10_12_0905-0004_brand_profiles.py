"""Спринт 3: профиль бренда и снимок бренда в генерации.

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-12 09:05:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "brand_profiles",
        sa.Column("id", sa.Integer(), nullable=False),
        # unique: у пользователя один профиль бренда
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("business_name", sa.String(length=80), nullable=False),
        sa.Column("logo_path", sa.String(length=255), nullable=True),
        sa.Column("primary_color", sa.String(length=7), nullable=False),
        sa.Column("secondary_color", sa.String(length=7), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )
    # Снимок бренда на момент генерации — история не меняется при правке профиля
    op.add_column("generations", sa.Column("brand_name", sa.String(length=80), nullable=True))
    op.add_column("generations", sa.Column("primary_color", sa.String(length=7), nullable=True))
    op.add_column("generations", sa.Column("secondary_color", sa.String(length=7), nullable=True))


def downgrade() -> None:
    op.drop_column("generations", "secondary_color")
    op.drop_column("generations", "primary_color")
    op.drop_column("generations", "brand_name")
    op.drop_table("brand_profiles")

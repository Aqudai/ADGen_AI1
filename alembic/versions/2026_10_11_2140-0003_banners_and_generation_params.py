"""Спринт 2: параметры генерации (текст, стиль, форматы, сцена) и таблица баннеров.

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-11 21:40:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def new_generation_columns() -> list[sa.Column]:
    """Новые поля генерации. Пустые у генераций Спринта 1, поэтому все nullable."""
    return [
        sa.Column("step", sa.String(length=20), nullable=True),
        sa.Column("promo_text", sa.Text(), nullable=True),
        sa.Column("style", sa.String(length=20), nullable=True),
        sa.Column("formats", sa.JSON(), nullable=True),
        sa.Column("logo_path", sa.String(length=255), nullable=True),
        sa.Column("scene_path", sa.String(length=255), nullable=True),
        sa.Column("scene_source", sa.String(length=20), nullable=True),
        sa.Column("scene_note", sa.Text(), nullable=True),
    ]


def upgrade() -> None:
    for column in new_generation_columns():
        op.add_column("generations", column)

    op.create_table(
        "banners",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("generation_id", sa.Uuid(), nullable=False),
        sa.Column("format", sa.String(length=20), nullable=False),
        sa.Column("variant", sa.String(length=20), nullable=False),
        sa.Column("image_path", sa.String(length=255), nullable=False),
        # Удалили генерацию — удалятся и её баннеры
        sa.ForeignKeyConstraint(["generation_id"], ["generations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_banners_generation_id", "banners", ["generation_id"])


def downgrade() -> None:
    op.drop_index("ix_banners_generation_id", table_name="banners")
    op.drop_table("banners")
    for column in reversed(new_generation_columns()):
        op.drop_column("generations", column.name)

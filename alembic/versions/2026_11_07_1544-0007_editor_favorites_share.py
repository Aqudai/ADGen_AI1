"""Редактор («Ещё варианты», «Другие цвета», «Изменить»), избранное и ссылка «поделиться».

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-07 15:44:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Генерация, от которой сделана эта (при удалении родителя ссылка просто обнулится)
    op.add_column("generations", sa.Column("parent_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_generations_parent_id", "generations", "generations", ["parent_id"], ["id"],
        ondelete="SET NULL",
    )
    op.add_column(
        "generations", sa.Column("template_shift", sa.Integer(), server_default="0", nullable=False)
    )
    op.add_column(
        "generations", sa.Column("palette_shift", sa.Integer(), server_default="0", nullable=False)
    )
    op.add_column("generations", sa.Column("share_token", sa.String(length=32), nullable=True))
    op.create_unique_constraint("uq_generations_share_token", "generations", ["share_token"])
    op.add_column(
        "banners", sa.Column("favorite", sa.Boolean(), server_default=sa.false(), nullable=False)
    )


def downgrade() -> None:
    op.drop_column("banners", "favorite")
    op.drop_constraint("uq_generations_share_token", "generations", type_="unique")
    op.drop_column("generations", "share_token")
    op.drop_column("generations", "palette_shift")
    op.drop_column("generations", "template_shift")
    op.drop_constraint("fk_generations_parent_id", "generations", type_="foreignkey")
    op.drop_column("generations", "parent_id")

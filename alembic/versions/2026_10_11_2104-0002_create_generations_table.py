"""Спринт 1: таблица генераций (загруженное фото и результат обработки).

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-11 21:04:31
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "generations",
        sa.Column("id", sa.Uuid(), nullable=False),
        # До Спринта 3 генерации анонимные, поэтому user_id может быть пустым
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("source_path", sa.String(length=255), nullable=False),
        sa.Column("cutout_path", sa.String(length=255), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    # Индекс для страницы «История»: быстро находим генерации пользователя
    op.create_index("ix_generations_user_id", "generations", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_generations_user_id", table_name="generations")
    op.drop_table("generations")

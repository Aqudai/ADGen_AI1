"""Пожелание к дизайну и как мы его поняли (варианты дизайна).

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-05 23:53:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # «Уютно, по-осеннему, шрифт с засечками» — как написал пользователь
    op.add_column("generations", sa.Column("design_request", sa.Text(), nullable=True))
    # Результат разбора: настроение, цвета, шрифт и дизайн-задания вариантов
    op.add_column("generations", sa.Column("design", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("generations", "design")
    op.drop_column("generations", "design_request")

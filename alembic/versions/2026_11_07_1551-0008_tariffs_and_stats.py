"""Тарифы (users.is_pro) и время окончания генерации для статистики.

Revision ID: 0008
Revises: 0007
Create Date: 2026-11-07 15:51:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users", sa.Column("is_pro", sa.Boolean(), server_default=sa.false(), nullable=False)
    )
    op.add_column(
        "generations", sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("generations", "finished_at")
    op.drop_column("users", "is_pro")

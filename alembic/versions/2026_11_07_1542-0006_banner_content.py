"""Содержание баннера: казахский текст, цены, срок, призыв, контакты и QR-код.

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-07 15:42:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def generation_columns() -> list[sa.Column]:
    """Новые поля генерации — все необязательные."""
    return [
        sa.Column("text_kz", sa.Text(), nullable=True),
        sa.Column("price", sa.String(length=30), nullable=True),
        sa.Column("old_price", sa.String(length=30), nullable=True),
        sa.Column("deadline", sa.String(length=60), nullable=True),
        sa.Column("cta", sa.String(length=40), nullable=True),
        # Снимок контактов и ссылки для QR из профиля бренда
        sa.Column("contacts", sa.String(length=100), nullable=True),
        sa.Column("qr_url", sa.String(length=300), nullable=True),
    ]


def upgrade() -> None:
    op.add_column("brand_profiles", sa.Column("contacts", sa.String(length=100), nullable=True))
    op.add_column("brand_profiles", sa.Column("qr_url", sa.String(length=300), nullable=True))
    for column in generation_columns():
        op.add_column("generations", column)


def downgrade() -> None:
    for column in reversed(generation_columns()):
        op.drop_column("generations", column.name)
    op.drop_column("brand_profiles", "qr_url")
    op.drop_column("brand_profiles", "contacts")

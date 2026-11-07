"""Тарифы: на бесплатном — FREE_DAILY_LIMIT генераций в день, на Pro — без ограничений.

Так в MVP показана модель монетизации. Настоящая оплата не подключена: Pro включает
администратор на странице /admin (или кнопка «Попробовать Pro» в демо-режиме на /pricing).
"""

from datetime import UTC, datetime, time

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Generation, User


def used_today(db: Session, user: User) -> int:
    """Сколько генераций пользователь сделал сегодня (по UTC)."""
    start = datetime.combine(datetime.now(UTC).date(), time.min, tzinfo=UTC)
    return (
        db.scalar(
            select(func.count())
            .select_from(Generation)
            .where(Generation.user_id == user.id, Generation.created_at >= start)
        )
        or 0
    )


def limit_reached(db: Session, user: User) -> bool:
    return not user.is_pro and used_today(db, user) >= settings.free_daily_limit


LIMIT_MESSAGE = (
    "На бесплатном тарифе — {limit} генераций в день, сегодняшний лимит исчерпан. "
    "Подключите Pro или возвращайтесь завтра."
)

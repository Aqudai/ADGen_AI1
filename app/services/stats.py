"""Статистика для администратора: метрики продукта на одной странице.

Объём данных в MVP небольшой, поэтому считаем в Python по простым запросам —
так код легко читать. При росте сервиса эти подсчёты переносятся в SQL (GROUP BY).
"""

from collections import Counter
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Banner, Generation, GenerationStatus, User
from app.services.design import MOODS
from app.services.presets import FORMATS, VARIANTS
from app.services.templates import TEMPLATES

MOOD_LABELS = {mood.key: mood.label for mood in MOODS}


def collect(db: Session, days: int = 14) -> dict:
    now = datetime.now(UTC)
    generations = db.scalars(select(Generation)).all()
    banners = db.execute(select(Banner.variant, Banner.format, Banner.favorite)).all()

    done = [g for g in generations if g.status == GenerationStatus.DONE]
    failed = [g for g in generations if g.status == GenerationStatus.FAILED]
    durations = [
        (g.finished_at - g.created_at).total_seconds()
        for g in done
        if g.finished_at and g.created_at
    ]

    # Генерации по дням за последние days дней — для столбчатой диаграммы
    per_day = Counter(g.created_at.date() for g in generations if g.created_at)
    timeline = []
    for i in range(days - 1, -1, -1):
        day = (now - timedelta(days=i)).date()
        timeline.append({"label": day.strftime("%d.%m"), "count": per_day.get(day, 0)})
    peak = max((d["count"] for d in timeline), default=0) or 1

    templates = Counter(variant.split("-")[0] for variant, _, _ in banners)
    favorites = Counter(variant.split("-")[0] for variant, _, favorite in banners if favorite)
    formats = Counter(fmt for _, fmt, _ in banners)
    moods = Counter((g.design or {}).get("mood") for g in generations if g.design)

    return {
        "users": db.scalar(select(func.count()).select_from(User)) or 0,
        "pro_users": db.scalar(select(func.count()).select_from(User).where(User.is_pro)) or 0,
        "generations": len(generations),
        "today": per_day.get(now.date(), 0),
        "banners": len(banners),
        "failed_percent": round(100 * len(failed) / len(generations)) if generations else 0,
        "avg_seconds": round(sum(durations) / len(durations), 1) if durations else None,
        "with_request_percent": round(
            100 * sum(1 for g in generations if g.design_request) / len(generations)
        )
        if generations
        else 0,
        "shared": sum(1 for g in generations if g.share_token),
        "timeline": timeline,
        "peak": peak,
        "templates": [
            (TEMPLATES[k].label if k in TEMPLATES else VARIANTS.get(k, k), n, favorites.get(k, 0))
            for k, n in templates.most_common()
        ],
        "formats": [(FORMATS[k].label if k in FORMATS else k, n) for k, n in formats.most_common()],
        "moods": [(MOOD_LABELS.get(k, k), n) for k, n in moods.most_common() if k],
    }

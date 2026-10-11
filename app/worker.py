"""Celery-приложение для фоновых задач (генерация баннеров идёт здесь, а не в веб-запросе).

Запуск воркера: celery -A app.worker:celery_app worker --loglevel=info
"""

from celery import Celery

from app.config import settings

celery_app = Celery(
    "adgen",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.tasks"],
)
celery_app.conf.update(
    task_track_started=True,  # статус STARTED понадобится для отображения прогресса
    result_expires=60 * 60 * 24,  # результаты задач храним в Redis сутки
    broker_connection_retry_on_startup=True,  # ждать Redis, если он стартует позже воркера
)

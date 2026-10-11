"""Фоновые задачи Celery."""

from app.worker import celery_app


@celery_app.task
def ping() -> str:
    """Тестовая задача: проверяем, что воркер принимает и выполняет задачи."""
    return "pong"

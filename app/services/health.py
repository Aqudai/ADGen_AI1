"""Проверка состояния компонентов: база, Redis, воркер Celery."""

import redis
from sqlalchemy import text

from app.config import settings
from app.db import engine
from app.worker import celery_app


def check_database() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def check_redis() -> bool:
    try:
        client = redis.Redis.from_url(settings.redis_url, socket_connect_timeout=1)
        return bool(client.ping())
    except Exception:
        return False


def check_celery() -> bool:
    """Воркер жив, если ответил на ping в течение секунды."""
    try:
        return bool(celery_app.control.ping(timeout=1.0))
    except Exception:
        return False


def run_checks() -> dict[str, bool]:
    redis_ok = check_redis()
    return {
        "database": check_database(),
        "redis": redis_ok,
        # без Redis воркер недоступен по определению — не ждём таймаут зря
        "celery": redis_ok and check_celery(),
    }

"""Фоновые задачи Celery."""

import uuid

from celery.utils.log import get_task_logger
from PIL import Image

from app.db import SessionLocal
from app.models import Generation, GenerationStatus
from app.services import storage
from app.services.background import remove_background
from app.worker import celery_app

logger = get_task_logger(__name__)


@celery_app.task
def ping() -> str:
    """Тестовая задача: проверяем, что воркер принимает и выполняет задачи."""
    return "pong"


@celery_app.task(soft_time_limit=180)
def process_generation(generation_id: str) -> None:
    """Обработка загруженного фото в фоне.

    Спринт 1: удаляем фон. В Спринте 2 сюда добавятся генерация сцены,
    композиция, текст и экспорт в форматы.
    """
    with SessionLocal() as db:
        generation = db.get(Generation, uuid.UUID(generation_id))
        if generation is None:
            logger.warning("Генерация %s не найдена", generation_id)
            return

        generation.status = GenerationStatus.PROCESSING
        db.commit()  # сразу сохраняем, чтобы страница показала «Удаляем фон…»

        try:
            with Image.open(storage.media_path(generation.source_path)) as source:
                cutout = remove_background(source)
            cutout_path = storage.generation_file(generation.id, "cutout.png")
            storage.save_image(cutout, cutout_path, format="PNG")

            generation.cutout_path = cutout_path
            generation.status = GenerationStatus.DONE
        except Exception:
            # Подробности — в лог воркера, пользователю — понятное сообщение
            logger.exception("Ошибка обработки генерации %s", generation_id)
            generation.status = GenerationStatus.FAILED
            generation.error_message = "Не удалось обработать фото. Попробуйте другое изображение."
        db.commit()

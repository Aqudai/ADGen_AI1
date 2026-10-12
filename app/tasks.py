"""Фоновые задачи Celery."""

import uuid

from celery.utils.log import get_task_logger
from PIL import Image
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import Banner, Generation, GenerationStatus, GenerationStep
from app.services import storage
from app.services.background import remove_background
from app.services.banner import render_banner
from app.services.presets import FORMATS, STYLES
from app.services.scene import generate_scene
from app.worker import celery_app

logger = get_task_logger(__name__)


@celery_app.task
def ping() -> str:
    """Тестовая задача: проверяем, что воркер принимает и выполняет задачи."""
    return "pong"


def set_step(db: Session, generation: Generation, step: GenerationStep) -> None:
    """Сохраняем шаг сразу — страница результата покажет, что сейчас происходит."""
    generation.step = step
    db.commit()


# Ограничение времени задачи: удаление фона и сборка — секунды, нейросеть — до HF_TIMEOUT (90 с).
# Если что-то зависнет дольше, Celery прервёт ожидание, и сцена будет нарисована без нейросети.
@celery_app.task(soft_time_limit=180)
def process_generation(generation_id: str) -> None:
    """Полный пайплайн: удаление фона → сцена → баннеры всех выбранных форматов."""
    with SessionLocal() as db:
        generation = db.get(Generation, uuid.UUID(generation_id))
        if generation is None:
            logger.warning("Генерация %s не найдена", generation_id)
            return

        generation.status = GenerationStatus.PROCESSING
        try:
            # 1. Удаляем фон с фото товара
            set_step(db, generation, GenerationStep.CUTOUT)
            with Image.open(storage.media_path(generation.source_path)) as source:
                cutout = remove_background(source)
            generation.cutout_path = storage.generation_file(generation.id, "cutout.png")
            storage.save_image(cutout, generation.cutout_path, format="PNG")

            # 2. Сцена: одна на все форматы — экономим бесплатные кредиты нейросети
            set_step(db, generation, GenerationStep.SCENE)
            seed = generation.id.int % 2**31  # один и тот же фон при повторной обработке
            scene = generate_scene(generation.style, seed)
            generation.scene_path = storage.generation_file(generation.id, "scene.jpg")
            storage.save_image(scene.image, generation.scene_path, format="JPEG", quality=92)
            generation.scene_source = scene.source
            generation.scene_note = scene.note

            # 3. Баннеры: каждый выбранный формат × каждый вариант оформления
            set_step(db, generation, GenerationStep.COMPOSE)
            logo = None
            if generation.logo_path:
                logo = Image.open(storage.media_path(generation.logo_path)).convert("RGBA")
            for format_key in generation.formats:
                for variant in FORMATS[format_key].variants:
                    image = render_banner(
                        scene.image,
                        cutout,
                        generation.promo_text,
                        STYLES[generation.style],
                        FORMATS[format_key],
                        variant,
                        logo=logo,
                    )
                    path = storage.generation_file(generation.id, f"{format_key}-{variant}.jpg")
                    storage.save_image(image, path, format="JPEG", quality=92)
                    generation.banners.append(
                        Banner(format=format_key, variant=variant, image_path=path)
                    )

            generation.status = GenerationStatus.DONE
        except Exception:
            # Подробности — в лог воркера, пользователю — понятное сообщение
            logger.exception("Ошибка обработки генерации %s", generation_id)
            db.rollback()
            generation.status = GenerationStatus.FAILED
            generation.error_message = "Не удалось создать баннеры. Попробуйте другое фото."
        generation.step = None
        db.commit()

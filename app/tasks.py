"""Фоновые задачи Celery."""

import uuid
from collections import Counter
from datetime import UTC, datetime

from celery.utils.log import get_task_logger
from PIL import Image
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import Banner, Generation, GenerationStatus, GenerationStep, SceneSource
from app.services import storage
from app.services.animation import story_video
from app.services.background import remove_background
from app.services.banner import render_banner
from app.services.carousel import render_carousel
from app.services.design import interpret
from app.services.presets import FORMATS, STYLES
from app.services.scene import ai_scene_enabled, generate_ai_scene
from app.services.templates import Content, render_template
from app.services.text import name_logo
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


# Ограничение времени задачи: удаление фона и сборка — секунды, нейросеть — до HF_TIMEOUT (90 с)
@celery_app.task(soft_time_limit=180)
def process_generation(generation_id: str) -> None:
    """Пайплайн: удаление фона → (сцена нейросетью, если подключена) → баннеры по вариантам."""
    with SessionLocal() as db:
        generation = db.get(Generation, uuid.UUID(generation_id))
        if generation is None:
            logger.warning("Генерация %s не найдена", generation_id)
            return

        generation.status = GenerationStatus.PROCESSING
        try:
            # 1. Удаляем фон с фото товара (нужен шаблонам, где товар стоит на своём фоне).
            #    У «Ещё вариантов» и «Изменить» вырезка уже скопирована — второй раз не удаляем.
            set_step(db, generation, GenerationStep.CUTOUT)
            with Image.open(storage.media_path(generation.source_path)) as source:
                photo = source.convert("RGB")
            if generation.cutout_path and storage.media_path(generation.cutout_path).exists():
                cutout = Image.open(storage.media_path(generation.cutout_path)).convert("RGBA")
            else:
                cutout = remove_background(photo)
                generation.cutout_path = storage.generation_file(generation.id, "cutout.png")
                storage.save_image(cutout, generation.cutout_path, format="PNG")

            # 2. Понимаем пожелание к дизайну → 3–4 дизайн-задания
            brand = None
            if generation.primary_color and generation.secondary_color:
                brand = (generation.primary_color, generation.secondary_color)
            design = interpret(
                generation.design_request or "",
                generation.promo_text,
                brand,
                template_shift=generation.template_shift or 0,
                palette_shift=generation.palette_shift or 0,
                favorite=favorite_template(db, generation.user_id),
            )
            generation.design = design.to_dict()

            # 3. Сцена от нейросети — необязательный дополнительный вариант
            scene = None
            if ai_scene_enabled():
                set_step(db, generation, GenerationStep.SCENE)
                scene, generation.scene_note = generate_ai_scene(design.scene_style)
                if scene is not None:
                    generation.scene_path = storage.generation_file(generation.id, "scene.jpg")
                    storage.save_image(scene, generation.scene_path, format="JPEG", quality=92)
                    generation.scene_source = SceneSource.AI

            # 4. Баннеры: каждый вариант дизайна × каждый выбранный формат
            set_step(db, generation, GenerationStep.COMPOSE)
            logo = None
            if generation.logo_path:
                logo = Image.open(storage.media_path(generation.logo_path)).convert("RGBA")
            for number, spec in enumerate(design.variants, start=1):
                content = Content(
                    photo=photo,
                    cutout=cutout,
                    promo_text=generation.promo_text,
                    primary=spec.primary,
                    secondary=spec.secondary,
                    brand_name=generation.brand_name,
                    logo=logo,
                    font=spec.font,
                    text_kz=generation.text_kz,
                    price=generation.price,
                    old_price=generation.old_price,
                    deadline=generation.deadline,
                    cta=generation.cta,
                    contacts=generation.contacts,
                    qr_url=generation.qr_url,
                )
                variant = f"{spec.template}-{number}"
                if number == 1 and "video" in generation.formats:
                    story = render_template(spec.template, content, FORMATS["story"].size)
                    path = storage.generation_file(generation.id, "video-story.mp4")
                    storage.save_bytes(story_video(story), path)
                    # Обложка видео — тот же кадр картинкой (видна до запуска ролика)
                    storage.save_image(
                        story, path.removesuffix(".mp4") + ".jpg", format="JPEG", quality=88
                    )
                    generation.banners.append(
                        Banner(format="video", variant="video", image_path=path)
                    )
                if number == 1 and "carousel" in generation.formats:
                    # Карусель — одна, в стиле первого (лучше всего подходящего) варианта
                    for slide, image in enumerate(render_carousel(spec, content), start=1):
                        add_banner(generation, image, "carousel", "carousel", f"carousel-{slide}")
                for format_key in generation.formats:
                    if format_key in ("carousel", "video"):
                        continue
                    fmt = FORMATS[format_key]
                    image = render_template(
                        spec.template, content, fmt.size, clean=format_key == "2gis"
                    )
                    add_banner(generation, image, format_key, variant)

            if scene is not None:
                primary, secondary = design.variants[0].primary, design.variants[0].secondary
                if logo is None and generation.brand_name:
                    logo = name_logo(generation.brand_name, primary)
                for format_key in generation.formats:
                    if format_key in ("carousel", "video"):
                        continue
                    fmt = FORMATS[format_key]
                    image = render_banner(
                        scene,
                        cutout,
                        generation.promo_text,
                        STYLES[design.scene_style],
                        fmt,
                        "clean" if format_key == "2gis" else "overlay",
                        logo=logo,
                        accent=primary,
                        badge_color=secondary,
                    )
                    add_banner(generation, image, format_key, "ai")

            generation.status = GenerationStatus.DONE
        except Exception:
            # Подробности — в лог воркера, пользователю — понятное сообщение
            logger.exception("Ошибка обработки генерации %s", generation_id)
            db.rollback()
            generation.status = GenerationStatus.FAILED
            generation.error_message = "Не удалось создать баннеры. Попробуйте другое фото."
        generation.step = None
        generation.finished_at = datetime.now(UTC)
        db.commit()


def favorite_template(db: Session, user_id: int | None) -> str | None:
    """Тема, которую пользователь чаще всего отмечал звёздочкой («pop-1» → «pop»)."""
    if user_id is None:
        return None
    # Пары (генерация, вариант): у одного варианта несколько баннеров (пост, сторис, 2GIS)
    rows = db.execute(
        select(Banner.generation_id, Banner.variant)
        .join(Generation)
        .where(Generation.user_id == user_id, Banner.favorite)
        .distinct()
    ).all()
    counts = Counter(variant.split("-")[0] for _, variant in rows)
    return counts.most_common(1)[0][0] if counts else None


def add_banner(
    generation: Generation, image: Image.Image, format_key: str, variant: str, name: str = ""
) -> None:
    path = storage.generation_file(generation.id, f"{name or f'{variant}-{format_key}'}.jpg")
    storage.save_image(image, path, format="JPEG", quality=92)
    generation.banners.append(Banner(format=format_key, variant=variant, image_path=path))

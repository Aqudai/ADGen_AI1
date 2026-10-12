"""Шаг 2 пайплайна: фон-сцена для баннера.

По умолчанию сцену рисует нейросеть через Hugging Face (см. huggingface.py).
Если нейросеть недоступна — нет ключа, закончились бесплатные кредиты, нет интернета —
рисуем запасной фон программно (fallback_scene.py) и сохраняем причину, чтобы показать
её пользователю. Генерация баннеров не падает из-за внешнего сервиса.

Провайдер выбирается в .env: IMAGE_PROVIDER=huggingface или IMAGE_PROVIDER=fallback.
"""

import logging
from dataclasses import dataclass

from PIL import Image

from app.config import settings
from app.models import SceneSource
from app.services import huggingface
from app.services.fallback_scene import SCENE_SIZE, draw_fallback_scene
from app.services.presets import STYLES

logger = logging.getLogger(__name__)


@dataclass
class SceneResult:
    image: Image.Image
    source: SceneSource
    note: str | None = None  # почему без нейросети (None — всё штатно)


def generate_scene(style: str, seed: int) -> SceneResult:
    if settings.image_provider != "huggingface":
        return SceneResult(draw_fallback_scene(style, seed), SceneSource.FALLBACK)

    if not settings.hf_token:
        return fallback(style, seed, "не указан ключ Hugging Face (HF_TOKEN в .env)")

    try:
        image = huggingface.text_to_image(STYLES[style].prompt, SCENE_SIZE)
    except huggingface.SceneGenerationError as exc:
        # exc_info — в лог попадёт и исходная ошибка библиотеки, это поможет разобраться
        logger.warning("Нейросеть не нарисовала сцену: %s", exc, exc_info=True)
        return fallback(style, seed, str(exc))
    return SceneResult(image.convert("RGB"), SceneSource.AI)


def fallback(style: str, seed: int, note: str) -> SceneResult:
    return SceneResult(draw_fallback_scene(style, seed), SceneSource.FALLBACK, note)

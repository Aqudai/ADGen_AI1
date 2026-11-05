"""Необязательный вариант «Сцена от нейросети».

Если в .env указан ключ Hugging Face (HF_TOKEN) и на аккаунте есть кредиты, нейросеть
рисует фон-сцену, и к вариантам дизайна добавляется ещё один — товар на этой сцене.
Нет ключа — вариант просто не предлагается. Ошибка нейросети — вариант пропускается,
а причина показывается пользователю. Основные варианты (шаблоны) от нейросети не зависят.
"""

import logging

from PIL import Image

from app.config import settings
from app.services import huggingface
from app.services.presets import STYLES

logger = logging.getLogger(__name__)

SCENE_SIZE = 1024


def ai_scene_enabled() -> bool:
    return settings.image_provider == "huggingface" and bool(settings.hf_token)


def generate_ai_scene(style: str) -> tuple[Image.Image | None, str | None]:
    """Возвращает (сцена, None) или (None, причина, почему не получилось)."""
    try:
        image = huggingface.text_to_image(STYLES[style].prompt, SCENE_SIZE)
    except huggingface.SceneGenerationError as exc:
        # exc_info — в лог попадёт и исходная ошибка библиотеки, это поможет разобраться
        logger.warning("Нейросеть не нарисовала сцену: %s", exc, exc_info=True)
        return None, str(exc)
    return image.convert("RGB"), None

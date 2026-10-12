"""Генерация сцены нейросетью через Hugging Face (библиотека huggingface_hub).

Ключ — переменная HF_TOKEN в .env. Именно это имя читает и сама библиотека: перед
генерацией она делает служебный запрос «какие провайдеры обслуживают модель»,
и для него берёт ключ из HF_TOKEN.

Все ошибки превращаются в SceneGenerationError с понятным пользователю текстом —
тогда scene.py нарисует запасной фон и покажет причину.
"""

import httpx2
from huggingface_hub import InferenceClient
from huggingface_hub.errors import HfHubHTTPError, RepositoryNotFoundError
from PIL import Image, UnidentifiedImageError

from app.config import settings


class SceneGenerationError(Exception):
    """Нейросеть не нарисовала сцену. Текст ошибки показываем пользователю."""


def text_to_image(prompt: str, size: int) -> Image.Image:
    client = InferenceClient(
        provider=settings.hf_provider, api_key=settings.hf_token, timeout=settings.hf_timeout
    )
    try:
        # Передаём только описание и размер: разные провайдеры понимают разный набор
        # параметров, и лишний (negative_prompt, seed) может привести к отказу
        image = client.text_to_image(prompt, model=settings.hf_model, width=size, height=size)
        image.load()  # картинка открывается «лениво» — декодируем здесь, пока ловим ошибки
        return image
    # Порядок важен: RepositoryNotFoundError — подвид HfHubHTTPError, а тот — подвид ошибки httpx2
    except (TimeoutError, httpx2.TimeoutException) as exc:
        # В huggingface_hub 2.2 таймаут приходит как ошибка httpx2, а не InferenceTimeoutError
        raise SceneGenerationError("нейросеть не ответила вовремя") from exc
    except RepositoryNotFoundError as exc:
        raise SceneGenerationError(f"модель {settings.hf_model} не найдена (HF_MODEL)") from exc
    except HfHubHTTPError as exc:
        raise SceneGenerationError(http_error_message(exc.response.status_code)) from exc
    except ValueError as exc:
        # Неизвестный провайдер или модель, которую этот провайдер не обслуживает
        raise SceneGenerationError(f"неверные настройки HF_PROVIDER / HF_MODEL ({exc})") from exc
    except UnidentifiedImageError as exc:
        raise SceneGenerationError("нейросеть прислала не картинку") from exc
    except (httpx2.HTTPError, OSError) as exc:
        raise SceneGenerationError("нет связи с Hugging Face") from exc
    except Exception as exc:
        # Всё непредвиденное (например, сбой внутри библиотеки) — тоже не повод
        # ронять генерацию: нарисуем запасной фон, подробности будут в логе воркера
        raise SceneGenerationError("нейросеть недоступна") from exc
    finally:
        client.close()


def http_error_message(status: int) -> str:
    if status in (401, 403):
        return (
            "Hugging Face не принял ключ — проверьте HF_TOKEN и галочку "
            "«Make calls to Inference Providers»"
        )
    if status == 402:
        return "на аккаунте Hugging Face закончились кредиты на генерацию"
    if status == 429:
        return "Hugging Face просит подождать — слишком много запросов"
    if status >= 500:
        return f"сервис нейросети временно недоступен (ошибка {status})"
    return f"Hugging Face вернул ошибку {status}"

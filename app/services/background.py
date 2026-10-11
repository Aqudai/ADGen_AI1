"""Шаг 1 пайплайна: удаление фона с фото товара (rembg)."""

from functools import cache

from PIL import Image, ImageFilter

from app.config import settings


@cache
def _get_session(model_name: str):
    """Модель загружается в память один раз на процесс воркера и дальше переиспользуется.

    rembg импортируем здесь, а не в начале файла: веб-серверу эта тяжёлая
    библиотека не нужна, её использует только воркер.
    """
    from rembg import new_session

    return new_session(model_name)


def remove_background(image: Image.Image) -> Image.Image:
    """Возвращает RGBA-изображение того же размера: товар на прозрачном фоне."""
    from rembg import remove

    # post_process_mask убирает мелкий «мусор» из маски вне товара
    cutout = remove(image, session=_get_session(settings.rembg_model), post_process_mask=True)
    return soften_edges(cutout.convert("RGBA"))


def soften_edges(cutout: Image.Image) -> Image.Image:
    """Убирает тёмную кайму и «лесенку» по контуру товара.

    Маска после rembg захватывает 1–2 пикселя старого фона по краю. Сужаем её
    на пиксель (MinFilter) и слегка размываем край — товар ляжет на новый фон
    без ореола. Подобрано сравнением на тестовых фото, занимает ~0,1 с.
    """
    alpha = cutout.getchannel("A")
    alpha = alpha.filter(ImageFilter.MinFilter(3)).filter(ImageFilter.GaussianBlur(1))
    cutout.putalpha(alpha)
    return cutout

"""Проверка и подготовка загруженного фото."""

from typing import BinaryIO

from PIL import Image, ImageOps, UnidentifiedImageError

# MPO — это JPEG с несколькими кадрами внутри: так сохраняют фото многие телефоны и камеры
ALLOWED_FORMATS = {"JPEG", "MPO", "PNG", "WEBP"}
MIN_SIDE = 200  # меньше — товар не разглядеть, удаление фона даст плохой результат
MAX_SIDE = 2048  # больше не нужно для баннера 1080 px, а обработка станет медленнее


class ImageValidationError(ValueError):
    """Ошибка загрузки, текст которой можно показать пользователю."""


def prepare_source_image(file: BinaryIO) -> Image.Image:
    """Проверяет файл и возвращает фото, готовое к обработке.

    - убеждается, что это действительно JPG/PNG/WebP, а не файл с подменённым расширением;
    - поворачивает по EXIF (телефоны часто хранят фото «на боку» с пометкой о повороте);
    - уменьшает до MAX_SIDE по большей стороне;
    - убирает прозрачность (подкладывает белый фон) — исходник сохраняем в JPEG.
    """
    try:
        image = Image.open(file)
        image.load()  # полностью декодируем: так ловим обрезанные и битые файлы
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise ImageValidationError(
            "Не удалось открыть файл как изображение. Загрузите JPG, PNG или WebP."
        ) from exc

    if image.format not in ALLOWED_FORMATS:
        raise ImageValidationError("Поддерживаются только JPG, PNG и WebP.")

    image = ImageOps.exif_transpose(image)

    if min(image.size) < MIN_SIDE:
        raise ImageValidationError(
            f"Фото слишком маленькое ({image.width}×{image.height}). "
            f"Нужно хотя бы {MIN_SIDE} пикселей по каждой стороне."
        )

    image.thumbnail((MAX_SIDE, MAX_SIDE))
    return flatten_to_rgb(image)


def flatten_to_rgb(image: Image.Image) -> Image.Image:
    """RGB без прозрачности: прозрачные места становятся белыми, а не чёрными."""
    if image.mode in ("RGBA", "LA", "PA") or "transparency" in image.info:
        rgba = image.convert("RGBA")
        background = Image.new("RGB", rgba.size, "white")
        background.paste(rgba, mask=rgba.getchannel("A"))
        return background
    return image.convert("RGB")

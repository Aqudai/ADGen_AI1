"""Проверка и подготовка загруженного фото."""

from typing import BinaryIO

from PIL import Image, ImageOps, UnidentifiedImageError

# MPO — это JPEG с несколькими кадрами внутри: так сохраняют фото многие телефоны и камеры
ALLOWED_FORMATS = {"JPEG", "MPO", "PNG", "WEBP"}
MIN_SIDE = 200  # меньше — товар не разглядеть, удаление фона даст плохой результат
MAX_SIDE = 2048  # больше не нужно для баннера 1080 px, а обработка станет медленнее
LOGO_MAX_SIDE = 600  # логотип на баннере занимает не больше трети ширины
# Защита от «картинки-бомбы»: крошечный файл с огромным размером в пикселях, который при
# раскодировании съедает гигабайты памяти. 60 Мп хватает для фото с любого телефона.
MAX_PIXELS = 60_000_000


class ImageValidationError(ValueError):
    """Ошибка загрузки, текст которой можно показать пользователю."""


def open_image(file: BinaryIO, error_text: str) -> Image.Image:
    """Открывает и полностью декодирует картинку, проверив размер в пикселях заранее."""
    try:
        image = Image.open(file)  # читает только заголовок — размер известен без декодирования
        if image.width * image.height > MAX_PIXELS:
            raise ImageValidationError("Изображение слишком большое в пикселях — уменьшите его.")
        image.load()  # полностью декодируем: так ловим обрезанные и битые файлы
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise ImageValidationError(error_text) from exc
    return image


def prepare_source_image(file: BinaryIO) -> Image.Image:
    """Проверяет файл и возвращает фото, готовое к обработке.

    - убеждается, что это действительно JPG/PNG/WebP, а не файл с подменённым расширением;
    - поворачивает по EXIF (телефоны часто хранят фото «на боку» с пометкой о повороте);
    - уменьшает до MAX_SIDE по большей стороне;
    - убирает прозрачность (подкладывает белый фон) — исходник сохраняем в JPEG.
    """
    image = open_image(
        file, "Не удалось открыть файл как изображение. Загрузите JPG, PNG или WebP."
    )

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


def prepare_logo_image(file: BinaryIO) -> Image.Image:
    """Проверяет логотип. В отличие от фото, прозрачность сохраняем (логотипы часто PNG)."""
    image = open_image(
        file, "Не удалось открыть логотип как изображение. Загрузите PNG, JPG или WebP."
    )
    if image.format not in ALLOWED_FORMATS:
        raise ImageValidationError("Логотип: поддерживаются только PNG, JPG и WebP.")

    image = ImageOps.exif_transpose(image).convert("RGBA")
    if min(image.size) < 32:
        raise ImageValidationError("Логотип слишком маленький — нужно хотя бы 32 пикселя.")
    image.thumbnail((LOGO_MAX_SIDE, LOGO_MAX_SIDE))
    return image


def flatten_to_rgb(image: Image.Image) -> Image.Image:
    """RGB без прозрачности: прозрачные места становятся белыми, а не чёрными."""
    if image.mode in ("RGBA", "LA", "PA") or "transparency" in image.info:
        rgba = image.convert("RGBA")
        background = Image.new("RGB", rgba.size, "white")
        background.paste(rgba, mask=rgba.getchannel("A"))
        return background
    return image.convert("RGB")

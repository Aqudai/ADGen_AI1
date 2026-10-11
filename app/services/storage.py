"""Хранение файлов в папке media/.

В базе храним относительные пути вида "generations/<id>/source.jpg".
Если позже перейдём на S3-совместимое хранилище, менять нужно будет только этот модуль.
"""

import uuid
from pathlib import Path

from PIL import Image

from app.config import settings


def generation_file(generation_id: uuid.UUID, filename: str) -> str:
    """Относительный путь к файлу генерации."""
    return f"generations/{generation_id}/{filename}"


def media_path(rel_path: str) -> Path:
    """Полный путь к файлу на диске."""
    return settings.media_dir / rel_path


def media_url(rel_path: str) -> str:
    """Адрес файла для браузера (папка media/ раздаётся по /media)."""
    return f"/media/{rel_path}"


def save_image(image: Image.Image, rel_path: str, **save_options) -> None:
    """Сохраняет картинку, создавая папки при необходимости."""
    path = media_path(rel_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, **save_options)

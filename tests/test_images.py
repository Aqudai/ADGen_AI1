"""Проверка и подготовка загруженного фото (app/services/images.py)."""

import io

import pytest
from PIL import Image

from app.services.background import soften_edges
from app.services.images import ImageValidationError, prepare_source_image
from tests.conftest import make_image_bytes


def test_valid_jpeg_is_accepted():
    image = prepare_source_image(io.BytesIO(make_image_bytes((800, 600))))
    assert image.size == (800, 600)
    assert image.mode == "RGB"


def test_large_photo_is_downscaled():
    image = prepare_source_image(io.BytesIO(make_image_bytes((4000, 3000))))
    assert max(image.size) == 2048
    assert image.size == (2048, 1536)  # пропорции сохранены


def test_exif_rotation_is_applied():
    """Телефон сохранил фото 800×600 с пометкой «повернуть на 90°» — ждём 600×800."""
    buffer = io.BytesIO()
    exif = Image.Exif()
    exif[0x0112] = 6  # тег Orientation: повернуть на 90° по часовой
    Image.new("RGB", (800, 600), "blue").save(buffer, format="JPEG", exif=exif)
    image = prepare_source_image(io.BytesIO(buffer.getvalue()))
    assert image.size == (600, 800)


def test_transparent_png_gets_white_background():
    data = make_image_bytes((400, 400), color=(0, 0, 0, 0), fmt="PNG", mode="RGBA")
    image = prepare_source_image(io.BytesIO(data))
    assert image.mode == "RGB"
    assert image.getpixel((10, 10)) == (255, 255, 255)


def test_not_an_image_is_rejected():
    with pytest.raises(ImageValidationError, match="Не удалось открыть"):
        prepare_source_image(io.BytesIO(b"this is not an image"))


def test_unsupported_format_is_rejected():
    with pytest.raises(ImageValidationError, match="JPG, PNG и WebP"):
        prepare_source_image(io.BytesIO(make_image_bytes(fmt="GIF")))


@pytest.mark.filterwarnings("ignore::PIL.Image.DecompressionBombWarning")
def test_image_bomb_is_rejected_before_decoding():
    """PNG весом в килобайты, но 12000×12000 пикселей — отклоняем, не раскодируя."""
    buffer = io.BytesIO()
    Image.new("1", (12000, 12000)).save(buffer, format="PNG")
    assert len(buffer.getvalue()) < 100_000
    with pytest.raises(ImageValidationError, match="слишком большое в пикселях"):
        prepare_source_image(io.BytesIO(buffer.getvalue()))


def test_too_small_image_is_rejected():
    with pytest.raises(ImageValidationError, match="слишком маленькое"):
        prepare_source_image(io.BytesIO(make_image_bytes((150, 900))))


def test_soften_edges_shrinks_mask():
    """Край маски сдвигается внутрь: пиксель на старой границе становится прозрачнее."""
    cutout = Image.new("RGBA", (100, 100), (0, 0, 0, 0))
    cutout.paste((255, 0, 0, 255), (25, 25, 75, 75))
    result = soften_edges(cutout)
    assert result.getpixel((50, 50))[3] == 255  # центр товара непрозрачный
    assert result.getpixel((25, 50))[3] < 128  # бывший край стал полупрозрачным
    assert result.getpixel((5, 5))[3] == 0  # фон остался прозрачным

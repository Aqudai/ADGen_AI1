"""Интеграционный тест настоящей модели rembg.

Медленный (~5 с, нужна модель ~180 МБ — в Docker-образе она уже есть).
Пропустить: pytest -m "not slow"
"""

import pytest
from PIL import Image, ImageDraw

from app.services.background import remove_background


@pytest.mark.slow
def test_real_model_separates_object_from_background():
    image = Image.new("RGB", (600, 600), (235, 235, 235))  # светло-серый фон
    ImageDraw.Draw(image).ellipse((180, 150, 420, 450), fill=(200, 40, 40))  # красный «товар»

    cutout = remove_background(image)

    assert cutout.mode == "RGBA"
    assert cutout.size == image.size
    assert cutout.getpixel((300, 300))[3] == 255  # товар остался
    assert cutout.getpixel((20, 20))[3] == 0  # фон стал прозрачным

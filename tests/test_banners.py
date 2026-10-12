"""Сборка баннеров: текст, композиция, все форматы и варианты (app/services/banner.py, text.py)."""

import pytest
from PIL import Image

from app.services import compose, text
from app.services.banner import render_banner
from app.services.fallback_scene import draw_fallback_scene
from app.services.presets import FORMATS, STYLES

NBSP = " "


def make_cutout() -> Image.Image:
    """«Товар» — красный прямоугольник на прозрачном фоне с полями вокруг."""
    cutout = Image.new("RGBA", (400, 600), (0, 0, 0, 0))
    cutout.paste((200, 30, 30, 255), (100, 100, 300, 500))
    return cutout


@pytest.mark.parametrize(
    ("promo", "expected"),
    [
        ("Скидка 20% на всё", "−20%"),
        ("Только сегодня -15 %", "−15%"),
        ("Новинка недели", None),
    ],
)
def test_find_discount(promo, expected):
    assert text.find_discount(promo) == expected


def test_typography_keeps_words_together():
    result = text.apply_typography("Кофе — 990 ₸. Второй в подарок")
    assert f"Кофе{NBSP}—" in result  # тире не начинает строку
    assert f"990{NBSP}₸" in result  # число не отрывается от валюты
    assert f"в{NBSP}подарок" in result  # предлог не висит в конце строки


def test_fit_text_shrinks_long_text():
    short_font, _ = text.fit_text("Скидка", 800, 200, max_size=120, min_size=20)
    long_font, long_lines = text.fit_text("Очень длинный текст акции " * 4, 800, 200, 120, 20)
    assert long_font.size < short_font.size
    assert all(long_font.getlength(line) <= 800 for line in long_lines)


def test_emoji_is_dropped_instead_of_empty_boxes():
    """В шрифте нет эмодзи — без фильтра они рисуются пустыми квадратиками."""
    assert text.drop_missing_glyphs("Скидка 20% 🎉☕ 990 ₸") == "Скидка 20%  990 ₸"


def test_very_long_word_does_not_overflow():
    fnt, lines = text.fit_text("Суперраспродажа" + "а" * 30, 300, 400, max_size=80, min_size=30)
    assert len(lines) > 1  # слово разрезано
    assert all(fnt.getlength(line) <= 300 for line in lines)


def test_long_word_is_kept_whole_when_smaller_font_fits():
    fnt, lines = text.fit_text("Суперраспродажа", 500, 400, max_size=120, min_size=20)
    assert lines == ["Суперраспродажа"]


def test_crop_to_content_removes_transparent_margins():
    assert compose.crop_to_content(make_cutout()).size == (200, 400)


def test_product_stands_on_bottom_of_box():
    canvas = Image.new("RGBA", (1000, 1000), (255, 255, 255, 255))
    compose.place_product(canvas, make_cutout(), (100, 100, 900, 800))
    # Товар вписан по высоте рамки (700 px): занимает строки 100–799 и стоит на нижней границе
    red = (200, 30, 30)
    assert canvas.getpixel((500, 100))[:3] == red
    assert canvas.getpixel((500, 799))[:3] == red
    assert canvas.getpixel((500, 98))[:3] != red  # выше — только мягкая тень
    assert canvas.getpixel((500, 801))[:3] != red


@pytest.mark.parametrize("style", list(STYLES))
@pytest.mark.parametrize("format_key", list(FORMATS))
def test_every_format_and_variant_renders(style, format_key):
    fmt = FORMATS[format_key]
    scene = draw_fallback_scene(style, seed=3, size=256)  # маленькая сцена — тесты быстрее
    logo = Image.new("RGB", (300, 100), "navy")
    for variant in fmt.variants:
        banner = render_banner(
            scene, make_cutout(), "Скидка 20% на всё до пятницы", STYLES[style], fmt, variant, logo
        )
        assert banner.size == fmt.size
        assert banner.mode == "RGB"


def test_2gis_banner_has_no_text():
    """2GIS запрещает текст на фото: вариант clean — только сцена и товар."""
    fmt = FORMATS["2gis"]
    assert fmt.variants == ("clean",)
    scene = draw_fallback_scene("minimal", seed=3, size=256)
    with_text = render_banner(scene, make_cutout(), "Текст", STYLES["minimal"], fmt, "clean")
    other_text = render_banner(scene, make_cutout(), "Другое", STYLES["minimal"], fmt, "clean")
    assert with_text.tobytes() == other_text.tobytes()  # текст акции на картинку не влияет

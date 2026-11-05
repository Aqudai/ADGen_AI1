"""Понимание пожелания к дизайну по ключевым словам (app/services/design.py)."""

from app.services.design import ALL_TEMPLATES, VARIANT_COUNT, interpret
from app.services.templates import TEMPLATES


def test_all_templates_exist():
    assert set(ALL_TEMPLATES) == set(TEMPLATES)


def test_cozy_request():
    result = interpret("Уютно, по-осеннему, тёплые цвета")
    assert result.mood == "cozy"
    assert "уютно" in result.matched
    assert len(result.variants) == VARIANT_COUNT
    assert len({v.template for v in result.variants}) == VARIANT_COUNT  # все варианты разные


def test_premium_and_serif_font():
    result = interpret("Премиум, элегантно, шрифт с засечками")
    assert result.mood == "premium"
    assert result.font == "serif"
    assert result.variants[0].template == "luxe"
    assert all(v.font == "serif" for v in result.variants)


def test_named_colors_become_palette():
    result = interpret("Ярко, синий и жёлтый")
    assert result.colors == ["#EAB308", "#1D4ED8"] or result.colors == ["#1D4ED8", "#EAB308"]
    assert {result.variants[0].primary, result.variants[0].secondary} == {"#EAB308", "#1D4ED8"}


def test_one_color_keeps_mood_accents():
    result = interpret("красный")
    assert all(v.primary == "#DC2626" for v in result.variants)


def test_brand_colors_used_when_no_colors_named():
    result = interpret("минимализм", brand_colors=("#112233", "#AABBCC"))
    assert (result.variants[0].primary, result.variants[0].secondary) == ("#112233", "#AABBCC")


def test_empty_request_uses_promo_text():
    result = interpret("", promo_text="Скидка на капучино и выпечку")
    assert result.mood == "cozy"  # «капучино» не знаем, а «выпечку» — да


def test_unknown_request_gives_default_variants():
    result = interpret("абракадабра")
    assert result.mood == "bright"
    assert result.matched == []
    assert len(result.variants) == VARIANT_COUNT


def test_holiday_phrase():
    assert interpret("Новогодняя акция").mood == "festive"

"""Сборка готового баннера: сцена + товар с тенью + текст акции + бейдж скидки + логотип.

Раскладка задана данными (LAYOUTS), а не кодом: для каждой формы баннера (квадрат,
вертикальный) и каждого варианта указано, где стоит товар, где текст и т.д.
Координаты — доли от ширины и высоты, поэтому раскладка работает для любого размера.
"""

from dataclasses import dataclass

from PIL import Image, ImageDraw, ImageFilter, ImageStat

from app.services import compose, text
from app.services.presets import BannerFormat, Style

Rel = tuple[float, float, float, float]  # (left, top, right, bottom) в долях


@dataclass(frozen=True)
class Layout:
    product: Rel
    text: Rel
    logo: Rel
    badge: tuple[float, float, float]  # центр x, центр y (доли) и радиус (доля меньшей стороны)
    scrim: str | None = None  # вариант «текст на фоне»: сверху или снизу затемнить под текстом
    panel: Rel | None = None  # вариант «текст на плашке»: где плашка


LAYOUTS = {
    ("square", "overlay"): Layout(
        product=(0.18, 0.10, 0.82, 0.68),
        text=(0.07, 0.70, 0.93, 0.94),
        logo=(0.05, 0.05, 0.32, 0.15),
        badge=(0.84, 0.16, 0.11),
        scrim="bottom",
    ),
    ("square", "panel"): Layout(
        product=(0.20, 0.36, 0.80, 0.93),
        text=(0.09, 0.08, 0.91, 0.29),
        logo=(0.05, 0.85, 0.32, 0.95),
        badge=(0.83, 0.47, 0.10),
        panel=(0.05, 0.05, 0.95, 0.32),
    ),
    # Сторис: верхние и нижние ~13% экрана закрывает интерфейс Instagram (аватар, поле ответа),
    # поэтому текст, логотип и товар держим между 0.13 и 0.87 высоты
    ("tall", "overlay"): Layout(
        product=(0.15, 0.39, 0.85, 0.78),
        text=(0.08, 0.13, 0.92, 0.35),
        logo=(0.33, 0.80, 0.67, 0.86),
        badge=(0.80, 0.43, 0.12),
        scrim="top",
    ),
    ("tall", "panel"): Layout(
        product=(0.15, 0.21, 0.85, 0.62),
        text=(0.11, 0.68, 0.89, 0.84),
        logo=(0.06, 0.13, 0.40, 0.19),
        badge=(0.80, 0.24, 0.12),
        panel=(0.06, 0.65, 0.94, 0.87),
    ),
}


# Вариант «без текста»: товар в центральной области
CLEAN_PRODUCT_BOX = (0.22, 0.10, 0.78, 0.90)


def shape_of(fmt: BannerFormat) -> str:
    return "tall" if fmt.width / fmt.height < 0.8 else "square"


def to_px(rel: Rel, size: tuple[int, int]) -> compose.Box:
    w, h = size
    return (int(rel[0] * w), int(rel[1] * h), int(rel[2] * w), int(rel[3] * h))


def is_light(image: Image.Image, box: compose.Box) -> bool:
    """Светлый ли фон в этой области (по средней яркости)."""
    return ImageStat.Stat(image.crop(box).convert("L")).mean[0] > 150


def draw_scrim(canvas: Image.Image, side: str, color: tuple[int, int, int], max_alpha: int) -> None:
    """Плавное затемнение (или осветление) под текстом, чтобы текст читался на любой сцене."""
    w, h = canvas.size
    gradient = Image.linear_gradient("L")  # 0 сверху → 255 снизу
    if side == "bottom":
        mask, pos = gradient.resize((w, int(h * 0.5))), (0, h - int(h * 0.5))
    else:  # top
        mask, pos = gradient.rotate(180).resize((w, int(h * 0.45))), (0, 0)
    mask = mask.point(lambda v: v * max_alpha // 255)
    layer = Image.new("RGBA", mask.size, color + (0,))
    layer.putalpha(mask)
    canvas.alpha_composite(layer, pos)


def render_banner(
    scene: Image.Image,
    cutout: Image.Image,
    promo_text: str,
    style: Style,
    fmt: BannerFormat,
    variant: str,
    logo: Image.Image | None = None,
    accent: str | None = None,
) -> Image.Image:
    """Собирает один баннер. accent — цвет плашки/бейджа (по умолчанию из стиля)."""
    accent = accent or style.accent
    size = fmt.size
    short_side = min(size)

    # Сцена на весь баннер + лёгкое размытие: эффект глубины резкости, товар «выходит» вперёд
    canvas = (
        compose.cover(scene, size)
        .filter(ImageFilter.GaussianBlur(short_side / 540))
        .convert("RGBA")
    )

    if variant == "clean":
        # Без текста и логотипа (требование 2GIS): товар по центру, с полями —
        # разные устройства обрезают картинку по-разному
        compose.place_product(canvas, cutout, to_px(CLEAN_PRODUCT_BOX, size))
        return canvas.convert("RGB")

    layout = LAYOUTS[(shape_of(fmt), variant)]
    text_box = to_px(layout.text, size)

    if layout.scrim:
        light = is_light(canvas, text_box)
        draw_scrim(
            canvas, layout.scrim, (255, 255, 255) if light else (0, 0, 0), 200 if light else 185
        )
        text_color, shadow = ("#111827", False) if light else ("#FFFFFF", True)
        badge_fill, badge_text = accent, "#FFFFFF"
    else:
        panel = to_px(layout.panel, size)
        panel_layer = Image.new("RGBA", size, (0, 0, 0, 0))
        ImageDraw.Draw(panel_layer).rounded_rectangle(panel, radius=short_side // 28, fill=accent)
        panel_layer.putalpha(panel_layer.getchannel("A").point(lambda a: a * 240 // 255))
        canvas.alpha_composite(panel_layer)
        text_color, shadow = text.readable_text_color(accent), False
        badge_fill, badge_text = "#FFFFFF", accent

    compose.place_product(canvas, cutout, to_px(layout.product, size))

    text.draw_text_block(
        canvas,
        promo_text,
        text_box,
        color=text_color,
        max_size=int(short_side * 0.105),
        min_size=int(short_side * 0.04),
        shadow=shadow,
    )

    discount = text.find_discount(promo_text)
    if discount:
        bx, by, br = layout.badge
        text.draw_badge(
            canvas,
            discount,
            (int(bx * size[0]), int(by * size[1])),
            int(br * short_side),
            fill=badge_fill,
            text_color=badge_text,
        )

    if logo is not None:
        compose.place_logo(canvas, logo, to_px(layout.logo, size))

    return canvas.convert("RGB")

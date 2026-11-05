"""Дизайнерские шаблоны баннеров.

Каждый шаблон — это готовый макет, как у дизайнера: свой фон, шрифты, расположение
товара и текста. Пользователь выбирает шаблоны, а мы подставляем его фото, текст акции,
логотип и фирменные цвета.

Шаблоны:
- «Яркий» (pop)        — фирменный цвет, большой круг, огромная цифра скидки;
- «Фото» (photo)       — исходное фото на весь кадр, текст на затемнении снизу;
- «Премиум» (luxe)     — тёмный фон, луч света, отражение товара, золото и антиква;
- «Минимализм» (arch)  — светлый фон, арка фирменного цвета, строгая типографика;
- «Журнал» (split)     — кадр делится на цветной блок с текстом и фото;
- «Узор» (pattern)     — геометрический орнамент и светлая карточка, как открытка;
- «Классика» (editorial) — бумажный фон, антиква, фото в рамке;
- «Плакат» (poster)    — огромный узкий заголовок и полоса фото, как афиша.

Для 2GIS (вариант clean) каждый шаблон рисует только изображение — без текста и логотипов,
как требует 2GIS.
"""

from dataclasses import dataclass

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageOps

from app.services import compose, text
from app.services.text import FONTS_DIR, Face

UNBOUNDED_BLACK = Face(FONTS_DIR / "Unbounded.ttf", 900, 1.0)
UNBOUNDED_BOLD = Face(FONTS_DIR / "Unbounded.ttf", 700, 1.12)
PLAYFAIR = Face(FONTS_DIR / "PlayfairDisplay.ttf", 600, 1.1)
PLAYFAIR_BOLD = Face(FONTS_DIR / "PlayfairDisplay.ttf", 800, 1.0)
OSWALD = Face(FONTS_DIR / "Oswald.ttf", 700, 1.0)
OSWALD_MEDIUM = Face(FONTS_DIR / "Oswald.ttf", 500, 1.08)
MONTSERRAT = text.MONTSERRAT
MONTSERRAT_SEMIBOLD = Face(FONTS_DIR / "Montserrat-SemiBold.ttf")

GOLD = "#D6B26E"
INK = "#1C1917"
CREAM = "#F3EEE7"


@dataclass
class Content:
    """Всё, что подставляется в шаблон."""

    photo: Image.Image  # исходное фото (RGB)
    cutout: Image.Image  # товар без фона (RGBA)
    promo_text: str
    primary: str  # фирменные цвета
    secondary: str
    brand_name: str | None = None
    logo: Image.Image | None = None
    font: str | None = None  # шрифт заголовка из запроса: serif / condensed / rounded

    def face(self, default: Face) -> Face:
        """Шрифт заголовка: заказанный в запросе, иначе — шрифт шаблона."""
        return {"serif": PLAYFAIR, "condensed": OSWALD_MEDIUM, "rounded": UNBOUNDED_BOLD}.get(
            self.font, default
        )

    @property
    def discount(self) -> str | None:
        return text.find_discount(self.promo_text)

    @property
    def headline(self) -> str:
        """Текст без «Скидка 20%», когда скидка крупно нарисована отдельно:
        «Скидка 20% на роллы до пятницы» → «На роллы до пятницы»."""
        if not self.discount:
            return self.promo_text
        rest = text.DISCOUNT_PHRASE_RE.sub("", self.promo_text, count=1).strip(" ,.:—–-!")
        return rest[:1].upper() + rest[1:] if len(rest) >= 3 else self.promo_text


# ----------------------------------------------------------------------------- помощники


def mix(color: str, other: str, amount: float) -> tuple[int, int, int]:
    """Смесь двух цветов: amount=0 — первый цвет, 1 — второй."""
    a = Image.new("RGB", (1, 1), color).getpixel((0, 0))
    b = Image.new("RGB", (1, 1), other).getpixel((0, 0))
    return tuple(round(x + (y - x) * amount) for x, y in zip(a, b, strict=True))


def hex_color(rgb: tuple[int, int, int]) -> str:
    return "#{:02X}{:02X}{:02X}".format(*rgb)


def px(rel, size) -> compose.Box:
    w, h = size
    return (int(rel[0] * w), int(rel[1] * h), int(rel[2] * w), int(rel[3] * h))


def text_in_box(canvas, value, box, face, color, max_size, min_size, align="left", valign="top"):
    """Текст в рамке: автоподбор размера и перенос. Возвращает нижнюю границу текста."""
    left, top, right, bottom = box
    fnt, lines = text.fit_text(value, right - left, bottom - top, max_size, min_size, face)
    step = text.line_height(fnt, text.face_for(value, face).line_spacing)
    total = step * len(lines)
    y = (
        top
        + {"top": 0, "center": (bottom - top - total) // 2, "bottom": bottom - top - total}[valign]
    )
    draw = ImageDraw.Draw(canvas)
    for i, line in enumerate(lines):
        x = left
        if align == "center":
            x = left + (right - left - text.text_width(line, fnt)) / 2
        draw.text((x, y + i * step), line, font=fnt, fill=color)
    return y + total


def spaced(value: str) -> str:
    """Р А З Р Я Д К А — для маленьких подписей в премиальном стиле (между словами — шире)."""
    # Между словами — широкий пробел (U+2003): обычные пробелы при переносе схлопываются в один
    return "\u2003".join(" ".join(word) for word in value.upper().split())


def drop_shadow(canvas, image, position, offset, blur, opacity):
    """Мягкая тень от непрозрачной части картинки."""
    shadow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    silhouette = Image.new("RGBA", image.size, (0, 0, 0, 0))
    silhouette.putalpha(image.getchannel("A").point(lambda a: a * opacity // 255))
    shadow.paste(silhouette, (position[0] + offset[0], position[1] + offset[1]))
    canvas.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(blur)))


def fit_product(cutout: Image.Image, box: compose.Box) -> tuple[Image.Image, tuple[int, int]]:
    """Товар, вписанный в рамку: картинка и её левый верхний угол (по центру, снизу)."""
    product = compose.crop_to_content(cutout.convert("RGBA"))
    left, top, right, bottom = box
    scale = min((right - left) / product.width, (bottom - top) / product.height)
    product = product.resize(
        (max(1, int(product.width * scale)), max(1, int(product.height * scale))), Image.LANCZOS
    )
    return product, (left + (right - left - product.width) // 2, bottom - product.height)


def brand_mark(canvas, content: Content, box: compose.Box, color: str, face=MONTSERRAT_SEMIBOLD):
    """Логотип, а если его нет — название бизнеса текстом."""
    if content.logo is not None:
        compose.place_logo(canvas, content.logo, box)
    elif content.brand_name:
        text_in_box(canvas, content.brand_name.upper(), box, face, color, 40, 14, valign="center")


def radial_glow(size, center, radius, color, strength) -> Image.Image:
    layer = Image.new("RGBA", size, (0, 0, 0, 0))
    x, y = center
    ImageDraw.Draw(layer).ellipse((x - radius, y - radius, x + radius, y + radius), fill=color)
    layer.putalpha(layer.getchannel("A").point(lambda a: a * strength // 255))
    return layer.filter(ImageFilter.GaussianBlur(radius // 2))


def shape_of(size) -> str:
    w, h = size
    if w / h > 1.3:
        return "wide"
    return "tall" if w / h < 0.8 else "square"


# ----------------------------------------------------------------------------- шаблоны


def render_pop(c: Content, size, clean=False) -> Image.Image:
    """«Яркий»: фирменный цвет, большой светлый круг, товар чуть наклонён, огромная скидка."""
    w, h = size
    s = min(size)
    shape = shape_of(size)
    canvas = Image.new("RGBA", size, c.primary)
    ink = text.readable_text_color(c.primary)

    circle_center = {"square": (0.66, 0.6), "tall": (0.5, 0.63), "wide": (0.5, 0.5)}[shape]
    cx, cy = int(circle_center[0] * w), int(circle_center[1] * h)
    r = int(s * (0.40 if shape != "wide" else 0.46))
    draw = ImageDraw.Draw(canvas)
    draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=mix(c.primary, "#FFFFFF", 0.22))

    product_box = {
        "square": (0.40, 0.24, 0.96, 0.95),
        "tall": (0.08, 0.40, 0.92, 0.78),
        "wide": (0.25, 0.08, 0.75, 0.94),
    }[shape]
    product, pos = fit_product(c.cutout, px(product_box, size))
    product = product.rotate(-6, expand=True, resample=Image.BICUBIC)
    drop_shadow(canvas, product, pos, (0, int(s * 0.02)), int(s * 0.03), 110)
    canvas.alpha_composite(product, pos)
    if clean:
        return canvas.convert("RGB")

    if shape == "square":
        discount_box, headline_box, mark_box = (
            (0.06, 0.06, 0.62, 0.27),
            (0.06, 0.30, 0.46, 0.74),
            (0.06, 0.86, 0.36, 0.94),
        )
    else:
        discount_box, headline_box, mark_box = (
            (0.08, 0.13, 0.92, 0.24),
            (0.08, 0.25, 0.92, 0.38),
            (0.08, 0.815, 0.50, 0.865),
        )
    headline = c.headline.upper()
    if c.discount:
        text_in_box(canvas, c.discount, px(discount_box, size), UNBOUNDED_BLACK, ink, 280, 60)
    else:
        headline_box = (discount_box[0], discount_box[1], headline_box[2], headline_box[3])
    text_in_box(canvas, headline, px(headline_box, size), c.face(UNBOUNDED_BOLD), ink, 70, 24)
    brand_mark(canvas, c, px(mark_box, size), ink)
    return canvas.convert("RGB")


def render_photo(c: Content, size, clean=False) -> Image.Image:
    """«Фото»: исходное фото на весь кадр — без вырезания, максимально естественно."""
    w, h = size
    s = min(size)
    canvas = compose.cover(c.photo, size).convert("RGBA")
    if clean:
        return canvas.convert("RGB")
    shape = shape_of(size)

    # Затемнение снизу — под текстом; сверху слегка — под логотипом
    gradient = Image.linear_gradient("L").resize((w, int(h * 0.62)))
    bottom = Image.new("RGBA", gradient.size, (0, 0, 0, 0))
    bottom.putalpha(gradient.point(lambda v: v * 225 // 255))
    canvas.alpha_composite(bottom, (0, h - gradient.height))
    top = Image.new("RGBA", (w, int(h * 0.2)), (0, 0, 0, 0))
    top.putalpha(
        Image.linear_gradient("L").rotate(180).resize(top.size).point(lambda v: v * 90 // 255)
    )
    canvas.alpha_composite(top)

    margin = 0.07
    top_y = 0.06 if shape == "square" else 0.13
    mark_h = 0.07 if shape == "square" else 0.045
    brand_mark(canvas, c, px((margin, top_y, 0.5, top_y + mark_h), size), "#FFFFFF")

    if c.discount:
        r = int(s * 0.14)
        cx, cy = int(w * 0.80), int(h * (0.19 if shape == "square" else 0.24))
        sticker = Image.new("RGBA", (r * 2 + 8, r * 2 + 8), (0, 0, 0, 0))
        ImageDraw.Draw(sticker).ellipse((4, 4, r * 2 + 4, r * 2 + 4), fill=c.secondary)
        text_in_box(
            sticker,
            c.discount,
            (int(r * 0.32), int(r * 0.55), int(r * 1.68), int(r * 1.45)),
            UNBOUNDED_BLACK,
            text.readable_text_color(c.secondary),
            r,
            12,
            "center",
            "center",
        )
        sticker = sticker.rotate(12, expand=True, resample=Image.BICUBIC)
        drop_shadow(
            canvas, sticker, (cx - sticker.width // 2, cy - sticker.height // 2), (0, 8), 14, 90
        )
        canvas.alpha_composite(sticker, (cx - sticker.width // 2, cy - sticker.height // 2))

    text_bottom = 0.92 if shape == "square" else 0.84
    box = px((margin, text_bottom - 0.28, 1 - margin, text_bottom), size)
    ImageDraw.Draw(canvas).rectangle(
        (box[0], box[1] - int(s * 0.035), box[0] + int(s * 0.12), box[1] - int(s * 0.027)),
        fill=c.secondary,
    )
    text_in_box(
        canvas, c.promo_text, box, c.face(MONTSERRAT), "#FFFFFF", int(s * 0.1), 26, valign="bottom"
    )
    return canvas.convert("RGB")


def render_luxe(c: Content, size, clean=False) -> Image.Image:
    """«Премиум»: тёмный фон, луч света сверху, отражение товара, золото и антиква."""
    w, h = size
    s = min(size)
    shape = shape_of(size)
    canvas = Image.new("RGBA", size, "#0C0B0D")
    product_box = {
        "square": (0.24, 0.27, 0.76, 0.70),
        "tall": (0.14, 0.33, 0.86, 0.64),
        "wide": (0.30, 0.10, 0.70, 0.74),
    }[shape]
    pbox = px(product_box, size)
    center = ((pbox[0] + pbox[2]) // 2, (pbox[1] + pbox[3]) // 2)
    canvas.alpha_composite(
        radial_glow(size, center, int(s * 0.42), mix(GOLD, "#000000", 0.35), 200)
    )

    product, pos = fit_product(c.cutout, pbox)
    # Отражение на «зеркальном полу»: перевёрнутый товар, плавно исчезающий вниз
    # Отражение короче самого товара — иначе зайдёт под подпись
    reflection = ImageOps.flip(product).crop((0, 0, product.width, int(product.height * 0.45)))
    fade = (
        Image.linear_gradient("L")
        .rotate(180)
        .resize(reflection.size)
        .point(lambda v: v * 80 // 255)
    )
    reflection.putalpha(ImageChops.multiply(reflection.getchannel("A"), fade))
    canvas.alpha_composite(reflection, (pos[0], pos[1] + product.height + 2))
    canvas.alpha_composite(product, pos)
    if clean:
        return canvas.convert("RGB")

    inset = int(s * 0.035)
    ImageDraw.Draw(canvas).rectangle(
        (inset, inset, w - inset, h - inset), outline=GOLD, width=max(2, s // 540)
    )
    if shape == "square":
        mark_box, discount_box, headline_box = (
            (0.3, 0.07, 0.7, 0.12),
            (0.1, 0.12, 0.9, 0.25),
            (0.1, 0.80, 0.9, 0.92),
        )
    else:
        mark_box, discount_box, headline_box = (
            (0.25, 0.135, 0.75, 0.165),
            (0.1, 0.18, 0.9, 0.29),
            (0.1, 0.72, 0.9, 0.84),
        )

    if c.logo is not None:
        compose.place_logo(canvas, c.logo, px(mark_box, size))
    elif c.brand_name:
        text_in_box(
            canvas,
            spaced(c.brand_name),
            px(mark_box, size),
            MONTSERRAT_SEMIBOLD,
            GOLD,
            30,
            12,
            "center",
            "center",
        )
    if c.discount:
        text_in_box(
            canvas,
            c.discount,
            px(discount_box, size),
            PLAYFAIR_BOLD,
            GOLD,
            200,
            40,
            "center",
            "center",
        )
    text_in_box(
        canvas, c.headline, px(headline_box, size), PLAYFAIR, "#F5EFE6", 66, 24, "center", "center"
    )
    return canvas.convert("RGB")


def render_arch(c: Content, size, clean=False) -> Image.Image:
    """«Минимализм»: светлый фон, арка фирменного (смягчённого) цвета, строгий текст."""
    w, h = size
    s = min(size)
    shape = shape_of(size)
    canvas = Image.new("RGBA", size, CREAM)
    arch_rel = {
        "square": (0.47, 0.12, 0.95, 1.2),
        "tall": (0.14, 0.40, 0.86, 1.2),
        "wide": (0.30, 0.10, 0.70, 1.2),
    }[shape]
    left, top, right, bottom = px(arch_rel, size)
    arch_color = mix(c.primary, CREAM, 0.55)
    ImageDraw.Draw(canvas).rounded_rectangle(
        (left, top, right, bottom), radius=(right - left) // 2, fill=arch_color
    )

    product_box = (
        left + (right - left) * 0.06,
        top + (right - left) * 0.25,
        right - (right - left) * 0.06,
        min(h * 0.94, bottom),
    )
    product, pos = fit_product(c.cutout, tuple(int(v) for v in product_box))
    # Контактная тень под товаром
    shadow = Image.new("RGBA", size, (0, 0, 0, 0))
    ImageDraw.Draw(shadow).ellipse(
        (
            pos[0] + product.width * 0.1,
            pos[1] + product.height - s * 0.015,
            pos[0] + product.width * 0.9,
            pos[1] + product.height + s * 0.02,
        ),
        fill=(0, 0, 0, 70),
    )
    canvas.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(s * 0.015)))
    canvas.alpha_composite(product, pos)
    if clean:
        return canvas.convert("RGB")

    if shape == "square":
        mark_box, headline_box, pill_xy = (
            (0.06, 0.06, 0.32, 0.12),
            (0.06, 0.20, 0.43, 0.70),
            (0.06, 0.78),
        )
    else:
        mark_box, headline_box, pill_xy = (
            (0.08, 0.135, 0.5, 0.175),
            (0.08, 0.20, 0.92, 0.30),
            (0.08, 0.80),
        )
    brand_mark(canvas, c, px(mark_box, size), INK)
    bottom_y = text_in_box(
        canvas, c.headline, px(headline_box, size), c.face(MONTSERRAT), INK, int(s * 0.085), 24
    )

    if c.discount:
        pill_h = int(s * 0.1)
        fnt, _ = text.fit_text(
            c.discount, int(s * 0.4), int(pill_h * 0.62), pill_h, 14, UNBOUNDED_BOLD
        )
        pill_w = int(text.text_width(c.discount, fnt) + pill_h)
        x = int(pill_xy[0] * w)
        y = bottom_y + int(s * 0.05)  # сразу под заголовком
        draw = ImageDraw.Draw(canvas)
        draw.rounded_rectangle((x, y, x + pill_w, y + pill_h), radius=pill_h // 2, fill=c.secondary)
        draw.text(
            (x + pill_w / 2, y + pill_h / 2),
            c.discount,
            font=fnt,
            fill=text.readable_text_color(c.secondary),
            anchor="mm",
        )
    return canvas.convert("RGB")


def render_split(c: Content, size, clean=False) -> Image.Image:
    """«Журнал»: цветной блок с крупной типографикой рядом с фото."""
    w, h = size
    s = min(size)
    shape = shape_of(size)
    if clean:
        return compose.cover(c.photo, size)
    canvas = Image.new("RGBA", size, c.primary)
    ink = text.readable_text_color(c.primary)
    if shape == "square":
        photo_box = (int(w * 0.46), 0, w, h)
        panel = (0.06, 0.07, 0.42, 0.93)
    else:
        photo_box = (0, 0, w, int(h * 0.56))
        panel = (0.08, 0.60, 0.92, 0.86)
    photo = compose.cover(c.photo, (photo_box[2] - photo_box[0], photo_box[3] - photo_box[1]))
    canvas.paste(photo, photo_box[:2])
    # Тонкая полоса второго цвета на стыке
    line = max(4, s // 120)
    draw = ImageDraw.Draw(canvas)
    if shape == "square":
        draw.rectangle((photo_box[0] - line, 0, photo_box[0], h), fill=c.secondary)
    else:
        draw.rectangle((0, photo_box[3], w, photo_box[3] + line), fill=c.secondary)

    left, top, right, bottom = px(panel, size)
    mark_h = int(s * 0.06)
    brand_mark(canvas, c, (left, bottom - mark_h, right, bottom), ink, OSWALD_MEDIUM)
    y = top
    if c.discount:
        y = text_in_box(
            canvas,
            c.discount,
            (left, top, right, top + int((bottom - top) * 0.4)),
            OSWALD,
            c.secondary if c.secondary != c.primary else ink,
            260,
            50,
        )
        y += int(s * 0.02)
    text_in_box(
        canvas,
        c.headline.upper(),
        (left, y, right, bottom - mark_h - int(s * 0.03)),
        c.face(OSWALD_MEDIUM),
        ink,
        int(s * 0.09),
        22,
    )
    return canvas.convert("RGB")


def render_pattern(c: Content, size, clean=False) -> Image.Image:
    """«Узор»: геометрический орнамент из фигур в фирменных цветах и светлая карточка
    с товаром и текстом в центре — как открытка."""
    import random

    w, h = size
    s = min(size)
    shape = shape_of(size)
    colors = [c.primary, c.secondary, hex_color(mix(c.primary, "#FFFFFF", 0.45)), CREAM]
    canvas = Image.new("RGBA", size, c.primary)
    draw = ImageDraw.Draw(canvas)
    tile = s // 6
    rng = random.Random(len(c.promo_text))  # один и тот же текст — один и тот же узор
    for ty in range(0, h + tile, tile):
        for tx in range(0, w + tile, tile):
            bg, fg = rng.sample(colors, 2)
            box = (tx, ty, tx + tile, ty + tile)
            draw.rectangle(box, fill=bg)
            kind = rng.randrange(5)
            if kind == 0:
                draw.ellipse(box, fill=fg)
            elif kind == 1:  # половина круга
                draw.pieslice((tx, ty, tx + tile, ty + tile * 2 - 1), 180, 360, fill=fg)
            elif kind == 2:  # четверть круга из угла
                draw.pieslice((tx - tile, ty - tile, tx + tile, ty + tile), 0, 90, fill=fg)
            elif kind == 3:
                draw.polygon([(tx, ty + tile), (tx + tile, ty + tile), (tx + tile, ty)], fill=fg)
            else:
                draw.ellipse(
                    (tx + tile // 4, ty + tile // 4, tx + 3 * tile // 4, ty + 3 * tile // 4),
                    fill=fg,
                )

    inset = int(s * (0.07 if shape != "tall" else 0.06))
    top_inset = inset if shape != "tall" else int(h * 0.12)
    card = (inset, top_inset, w - inset, h - top_inset)
    drop_shadow(
        canvas,
        Image.new("RGBA", (card[2] - card[0], card[3] - card[1]), (0, 0, 0, 255)),
        card[:2],
        (0, int(s * 0.012)),
        int(s * 0.02),
        90,
    )
    draw.rounded_rectangle(card, radius=int(s * 0.04), fill="#FFFDF8")
    cw, ch = card[2] - card[0], card[3] - card[1]

    def in_card(rel):
        return (
            int(card[0] + rel[0] * cw),
            int(card[1] + rel[1] * ch),
            int(card[0] + rel[2] * cw),
            int(card[1] + rel[3] * ch),
        )

    product_rel = {
        "square": (0.15, 0.40, 0.85, 0.93),
        "tall": (0.1, 0.42, 0.9, 0.9),
        "wide": (0.25, 0.08, 0.75, 0.92),
    }[shape]
    product, pos = fit_product(c.cutout, in_card(product_rel))
    drop_shadow(canvas, product, pos, (0, int(s * 0.012)), int(s * 0.02), 80)
    canvas.alpha_composite(product, pos)
    if clean:
        return canvas.convert("RGB")

    title_rel = (0.08, 0.07, 0.92, 0.30) if shape == "square" else (0.08, 0.08, 0.92, 0.27)
    bottom_y = text_in_box(
        canvas,
        c.headline,
        in_card(title_rel),
        c.face(UNBOUNDED_BOLD),
        INK,
        int(s * 0.08),
        22,
        "center",
        "center",
    )
    if c.discount:
        pill_h = int(s * 0.085)
        fnt, _ = text.fit_text(
            c.discount, int(s * 0.4), int(pill_h * 0.6), pill_h, 14, UNBOUNDED_BLACK
        )
        pill_w = int(text.text_width(c.discount, fnt) + pill_h)
        x, y = (w - pill_w) // 2, bottom_y + int(s * 0.02)
        draw.rounded_rectangle((x, y, x + pill_w, y + pill_h), radius=pill_h // 2, fill=c.secondary)
        draw.text(
            (x + pill_w / 2, y + pill_h / 2),
            c.discount,
            font=fnt,
            fill=text.readable_text_color(c.secondary),
            anchor="mm",
        )
    brand_mark(
        canvas,
        c,
        in_card((0.06, 0.92, 0.5, 0.97) if shape == "square" else (0.08, 0.93, 0.5, 0.97)),
        INK,
    )
    return canvas.convert("RGB")


def render_editorial(c: Content, size, clean=False) -> Image.Image:
    """«Классика»: бумажный фон, крупный заголовок антиквой, фото в рамке, тонкие линейки —
    как обложка журнала."""
    w, h = size
    s = min(size)
    shape = shape_of(size)
    if clean:
        return compose.cover(c.photo, size)
    canvas = Image.new("RGBA", size, "#F5F1E8")
    draw = ImageDraw.Draw(canvas)
    m = int(w * 0.07)
    top = int(h * (0.05 if shape == "square" else 0.13))
    rule = max(2, s // 540)

    # Шапка: название бизнеса слева, тонкая линейка
    mark_h = int(s * 0.04)
    brand_mark(canvas, c, (m, top, w // 2, top + mark_h), INK)
    draw.line(
        (m, top + mark_h + int(s * 0.02), w - m, top + mark_h + int(s * 0.02)), fill=INK, width=rule
    )

    head_top = top + mark_h + int(s * 0.05)
    head_bottom = int(h * (0.47 if shape == "square" else 0.36))
    y = text_in_box(
        canvas,
        c.headline,
        (m, head_top, w - m, head_bottom),
        c.face(PLAYFAIR),
        INK,
        int(s * 0.11),
        26,
    )
    if c.discount:
        text_in_box(
            canvas,
            c.discount,
            (m, y + int(s * 0.01), w - m, y + int(s * 0.1)),
            PLAYFAIR_BOLD,
            c.secondary if text.luminance(c.secondary) < 150 else c.primary,
            int(s * 0.08),
            20,
        )

    photo_box = (
        m,
        int(h * (0.58 if shape == "square" else 0.46)),
        w - m,
        int(h * (0.95 if shape == "square" else 0.86)),
    )
    photo = compose.cover(c.photo, (photo_box[2] - photo_box[0], photo_box[3] - photo_box[1]))
    mask = Image.new("L", photo.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        (0, 0, photo.width - 1, photo.height - 1), radius=int(s * 0.025), fill=255
    )
    canvas.paste(photo, photo_box[:2], mask)
    # Цветная «закладка» фирменного цвета у края фото
    draw.rectangle(
        (
            photo_box[0],
            photo_box[1] - int(s * 0.02),
            photo_box[0] + int(s * 0.14),
            photo_box[1] - int(s * 0.012),
        ),
        fill=c.primary,
    )
    return canvas.convert("RGB")


def render_poster(c: Content, size, clean=False) -> Image.Image:
    """«Плакат»: огромный узкий заголовок на всю ширину, под ним полоса фото, мелкая подпись —
    как афиша."""
    w, h = size
    s = min(size)
    shape = shape_of(size)
    if clean:
        return compose.cover(c.photo, size)
    paper = "#FAFAF7"
    canvas = Image.new("RGBA", size, paper)
    draw = ImageDraw.Draw(canvas)
    m = int(w * 0.06)
    head = (
        m,
        int(h * (0.05 if shape == "square" else 0.13)),
        w - m,
        int(h * (0.40 if shape == "square" else 0.37)),
    )
    title = c.promo_text.upper()
    text_in_box(
        canvas,
        title,
        head,
        c.face(OSWALD) if c.font != "condensed" else OSWALD,
        INK,
        int(s * 0.2),
        30,
        valign="bottom",
    )

    photo_box = (m, head[3] + int(s * 0.03), w - m, int(h * (0.88 if shape == "square" else 0.80)))
    photo = compose.cover(c.photo, (photo_box[2] - photo_box[0], photo_box[3] - photo_box[1]))
    canvas.paste(photo, photo_box[:2])

    if c.discount:
        r = int(s * 0.11)
        cx, cy = photo_box[2] - r - int(s * 0.03), photo_box[1] + r + int(s * 0.03)
        draw.rectangle((cx - r, cy - r * 0.62, cx + r, cy + r * 0.62), fill=c.primary)
        text_in_box(
            canvas,
            c.discount,
            (cx - r + 10, int(cy - r * 0.5), cx + r - 10, int(cy + r * 0.5)),
            OSWALD,
            text.readable_text_color(c.primary),
            int(r * 0.9),
            14,
            "center",
            "center",
        )

    foot = (m, photo_box[3] + int(s * 0.02), w - m, photo_box[3] + int(s * 0.07))
    draw.line((foot[0], foot[1], foot[2], foot[1]), fill=INK, width=max(2, s // 540))
    brand_mark(
        canvas,
        c,
        (foot[0], foot[1] + int(s * 0.012), foot[0] + int(w * 0.45), foot[3]),
        INK,
        OSWALD_MEDIUM,
    )
    return canvas.convert("RGB")


@dataclass(frozen=True)
class Template:
    key: str
    label: str
    description: str
    render: object


TEMPLATES = {
    t.key: t
    for t in (
        Template("pop", "Яркий", "Фирменный цвет, крупная скидка", render_pop),
        Template("photo", "Фото", "Ваше фото на весь кадр", render_photo),
        Template("luxe", "Премиум", "Тёмный фон, золото, отражение", render_luxe),
        Template("arch", "Минимализм", "Светлый фон и арка", render_arch),
        Template("split", "Журнал", "Цветной блок и фото", render_split),
        Template("pattern", "Узор", "Орнамент и карточка, как открытка", render_pattern),
        Template("editorial", "Классика", "Антиква, фото в рамке, как журнал", render_editorial),
        Template("poster", "Плакат", "Огромный узкий заголовок, как афиша", render_poster),
    )
}


def render_template(key: str, content: Content, size, clean: bool = False) -> Image.Image:
    return TEMPLATES[key].render(content, size, clean)

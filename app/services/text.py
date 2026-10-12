"""Шаг 4 пайплайна: текст акции и бейдж скидки — рисуем программно (Pillow).

Нейросеть текст НЕ рисует: она путает буквы (особенно кириллицу) и цифры в цене.
Шрифт Montserrat (лицензия OFL) лежит в app/assets/fonts — поддерживает кириллицу,
казахские буквы и знак тенге ₸.
"""

import re
from functools import cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

FONTS_DIR = Path(__file__).resolve().parent.parent / "assets" / "fonts"
HEADLINE_FONT = FONTS_DIR / "Montserrat-ExtraBold.ttf"
LINE_SPACING = 1.12

# «-20%», «−15 %», «скидка 30%» → бейдж «−20%»
DISCOUNT_RE = re.compile(r"[-−–]?\s?(\d{1,2})\s?%")

Box = tuple[int, int, int, int]


@cache
def font(size: int, path: Path = HEADLINE_FONT) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(path), size)


def find_discount(text: str) -> str | None:
    match = DISCOUNT_RE.search(text)
    return f"−{match.group(1)}%" if match else None


def text_width(text: str, fnt: ImageFont.FreeTypeFont) -> float:
    return fnt.getlength(text)


NBSP = "\u00a0"  # неразрывный пробел: слова, соединённые им, не разносятся по строкам
# Короткие слова из букв (предлоги, союзы) привязываем к следующему: «в подарок», а не «в / подарок»
SHORT_WORD_RE = re.compile(r"(?<!\S)([^\W\d_]{1,2}) (?=\S)")
# Тире не должно начинать строку — привязываем его к предыдущему слову
DASH_RE = re.compile(r" ([—–-]) ")
# Число не отрывается от валюты и процентов: «990 ₸», «20 %»
NUMBER_UNIT_RE = re.compile(r"(\d) (?=[₸₽$€%]|тг|руб)")


@cache
def has_glyph(char: str) -> bool:
    """Есть ли символ в шрифте. Отсутствующий рисуется пустым квадратиком (например, эмодзи)."""
    probe = font(40)
    return char.isspace() or bytes(probe.getmask(char)) != bytes(probe.getmask("\ue000"))


def drop_missing_glyphs(text: str) -> str:
    return "".join(char for char in text if has_glyph(char))


def apply_typography(text: str) -> str:
    text = DASH_RE.sub(NBSP + r"\1 ", text)
    text = NUMBER_UNIT_RE.sub(r"\1" + NBSP, text)
    return SHORT_WORD_RE.sub(r"\1" + NBSP, text)


def split_long_word(word: str, fnt: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    """Слово шире рамки режем по буквам — иначе оно вылезет за край баннера."""
    parts, current = [], ""
    for char in word:
        if current and text_width(current + char, fnt) > max_width:
            parts.append(current)
            current = ""
        current += char
    return parts + [current]


def wrap(
    text: str, fnt: ImageFont.FreeTypeFont, max_width: int, split_words: bool = False
) -> list[str]:
    """Перенос по словам. Переносы строк, которые ввёл пользователь, сохраняются.

    split_words — резать слова шире рамки (крайний случай, см. fit_text).
    """
    lines = []
    for paragraph in apply_typography(drop_missing_glyphs(text)).splitlines() or [""]:
        current = ""
        # Делим только по обычным пробелам: неразрывный пробел держит слова вместе
        words = []
        for word in re.split(r"[ \t]+", paragraph.strip()):
            words += split_long_word(word, fnt, max_width) if split_words else [word]
        for word in words:
            candidate = f"{current} {word}".strip()
            if not current or text_width(candidate, fnt) <= max_width:
                current = candidate
            else:
                lines.append(current)
                current = word
        lines.append(current)
    return [line for line in lines if line] or [""]


def line_height(fnt: ImageFont.FreeTypeFont) -> int:
    ascent, descent = fnt.getmetrics()
    return int((ascent + descent) * LINE_SPACING)


def fit_text(text: str, width: int, height: int, max_size: int, min_size: int):
    """Подбирает самый крупный шрифт, при котором текст влезает в рамку.

    Возвращает (шрифт, строки). Если не влезает даже min_size (например, одно очень
    длинное слово) — берём min_size и режем слова, чтобы текст не вылез за край.
    """
    for size in range(max_size, min_size - 1, -2):
        fnt = font(size)
        lines = wrap(text, fnt, width)
        fits_width = all(text_width(line, fnt) <= width for line in lines)
        if fits_width and line_height(fnt) * len(lines) <= height:
            return fnt, lines
    fnt = font(min_size)
    return fnt, wrap(text, fnt, width, split_words=True)


def draw_text_block(
    canvas: Image.Image,
    text: str,
    box: Box,
    color: str,
    max_size: int,
    min_size: int,
    shadow: bool = False,
    valign: str = "center",
) -> None:
    """Рисует текст в рамке box: автоподбор размера, перенос строк, выравнивание влево."""
    left, top, right, bottom = box
    fnt, lines = fit_text(text, right - left, bottom - top, max_size, min_size)
    step = line_height(fnt)
    total = step * len(lines)
    y = (
        top
        + {"top": 0, "center": (bottom - top - total) // 2, "bottom": bottom - top - total}[valign]
    )

    if shadow:
        # Мягкая тень под буквами — текст читается на любом фоне
        layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(layer)
        for i, line in enumerate(lines):
            draw.text((left, y + i * step + 2), line, font=fnt, fill=(0, 0, 0, 150))
        canvas.alpha_composite(layer.filter(ImageFilter.GaussianBlur(max(2, fnt.size // 18))))

    draw = ImageDraw.Draw(canvas)
    for i, line in enumerate(lines):
        draw.text((left, y + i * step), line, font=fnt, fill=color)


def draw_badge(
    canvas: Image.Image,
    label: str,
    center: tuple[int, int],
    radius: int,
    fill: str,
    text_color: str = "#FFFFFF",
) -> None:
    """Круглый бейдж скидки, например «−20%»."""
    x, y = center
    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    draw.ellipse((x - radius, y - radius + 6, x + radius, y + radius + 6), fill=(0, 0, 0, 90))
    layer = layer.filter(ImageFilter.GaussianBlur(radius // 8))
    draw = ImageDraw.Draw(layer)
    draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=fill)
    canvas.alpha_composite(layer)

    fnt, _ = fit_text(label, int(radius * 1.45), int(radius * 0.9), max_size=radius, min_size=12)
    ImageDraw.Draw(canvas).text((x, y), label, font=fnt, fill=text_color, anchor="mm")


def readable_text_color(background: str) -> str:
    """Белый или почти чёрный текст — смотря что лучше читается на этом фоне."""
    r, g, b = Image.new("RGB", (1, 1), background).getpixel((0, 0))
    luminance = 0.299 * r + 0.587 * g + 0.114 * b
    return "#FFFFFF" if luminance < 160 else "#111827"

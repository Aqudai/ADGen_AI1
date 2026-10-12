"""Запасной фон без нейросети: рисуем сцену программно (Pillow).

Используется, когда нейросеть недоступна: нет ключа, закончились бесплатные кредиты
Hugging Face, нет интернета. Так сервис работает всегда, а на защите ничего не «падает».

Каждая сцена — градиент «стены», «поверхность стола» внизу и декор по стилю
(боке-огоньки, конфетти). seed делает картинку повторяемой: одна генерация — один фон.
"""

import random

from PIL import Image, ImageDraw, ImageFilter

SCENE_SIZE = 1024
TABLE_TOP = 0.64  # где начинается поверхность стола (доля высоты) — на неё «ставим» товар


def vertical_gradient(size: tuple[int, int], top: str, bottom: str) -> Image.Image:
    """Плавный переход цвета сверху вниз."""
    mask = Image.linear_gradient("L").resize(size)
    return Image.composite(Image.new("RGB", size, bottom), Image.new("RGB", size, top), mask)


def add_bokeh(image: Image.Image, rng: random.Random, colors, count, radius, area, blur) -> None:
    """Размытые светящиеся круги — эффект «огоньков не в фокусе»."""
    layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    w, h = image.size
    for _ in range(count):
        r = rng.randint(*radius)
        x = rng.randint(0, w)
        y = rng.randint(int(area[0] * h), int(area[1] * h))
        color = rng.choice(colors)
        draw.ellipse((x - r, y - r, x + r, y + r), fill=color + (rng.randint(50, 130),))
    blurred = layer.filter(ImageFilter.GaussianBlur(blur))
    image.paste(blurred, mask=blurred)


def add_glow(image: Image.Image, center, radius: int, color: str, strength: int) -> None:
    """Мягкое пятно света (окно, лампа)."""
    layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
    x, y = center
    ImageDraw.Draw(layer).ellipse((x - radius, y - radius, x + radius, y + radius), fill=color)
    alpha = layer.getchannel("A").point(lambda a: a * strength // 255)
    layer.putalpha(alpha)
    blurred = layer.filter(ImageFilter.GaussianBlur(radius // 2))
    image.paste(blurred, mask=blurred)


def add_table(image: Image.Image, top: str, bottom: str, rng: random.Random, grain: bool) -> None:
    """Поверхность стола в нижней части кадра (+ волокна дерева для уютного стиля)."""
    w, h = image.size
    y0 = int(TABLE_TOP * h)
    table = vertical_gradient((w, h - y0), top, bottom)
    if grain:
        draw = ImageDraw.Draw(table, "RGBA")
        for _ in range(140):
            y = rng.randint(0, h - y0)
            shade = rng.choice([(0, 0, 0, 22), (255, 255, 255, 14)])
            draw.line((0, y, w, y + rng.randint(-6, 6)), fill=shade, width=rng.randint(1, 3))
        table = table.filter(ImageFilter.GaussianBlur(1))
    image.paste(table, (0, y0))
    # Светлая кромка стола и мягкая тень под ней — чтобы поверхность читалась
    draw = ImageDraw.Draw(image, "RGBA")
    draw.line((0, y0, w, y0), fill=(255, 255, 255, 60), width=3)


def add_confetti(image: Image.Image, rng: random.Random, colors, count: int) -> None:
    w, h = image.size
    for _ in range(count):
        piece = Image.new(
            "RGBA", (rng.randint(8, 18), rng.randint(16, 34)), rng.choice(colors) + (230,)
        )
        piece = piece.rotate(rng.randint(0, 180), expand=True, resample=Image.BICUBIC)
        x = rng.randint(0, w)
        y = rng.randint(0, int(TABLE_TOP * h * 0.95))
        image.paste(piece, (x, y), piece)


def add_vignette(image: Image.Image, strength: int) -> None:
    """Затемнение по краям — взгляд собирается в центре, где товар."""
    w, h = image.size
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).ellipse((-w * 0.25, -h * 0.25, w * 1.25, h * 1.25), fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(w // 6))
    dark = Image.new("RGB", (w, h), "black")
    image.paste(Image.blend(image, dark, strength / 255), mask=mask.point(lambda a: 255 - a))


def draw_fallback_scene(style: str, seed: int, size: int = SCENE_SIZE) -> Image.Image:
    rng = random.Random(seed)
    s = (size, size)

    if style == "cozy":
        image = vertical_gradient(s, "#2B1A12", "#7A4A2A")
        add_glow(
            image, (int(size * rng.uniform(0.2, 0.8)), int(size * 0.18)), size // 3, "#FFC58A", 150
        )
        warm = [(255, 207, 138), (255, 179, 92), (255, 241, 201)]
        add_bokeh(image, rng, warm, 28, (14, 60), (0.0, 0.6), 10)
        add_table(image, "#9A6638", "#5C3A20", rng, grain=True)
        add_vignette(image, 110)
    elif style == "festive":
        image = vertical_gradient(s, "#3A0A2E", "#9B1440")
        gold = [(255, 211, 107), (255, 231, 163), (255, 159, 184)]
        add_bokeh(image, rng, gold, 40, (10, 55), (0.0, 0.62), 8)
        confetti = [(255, 211, 107), (255, 255, 255), (255, 105, 160), (64, 224, 208)]
        add_confetti(image, rng, confetti, 70)
        add_table(image, "#5E0F27", "#2E0614", rng, grain=False)
        add_vignette(image, 100)
    else:  # minimal
        image = vertical_gradient(s, "#F5F0EA", "#E7DED3")
        add_glow(image, (size // 2, int(size * 0.3)), size // 2, "#FFFFFF", 120)
        add_table(image, "#E4D8CA", "#D2C3B1", rng, grain=False)
        add_vignette(image, 25)

    return image

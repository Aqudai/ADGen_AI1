"""Карусель для Instagram: 4 слайда 1080×1350, которые листают вправо.

1. Обложка — первый вариант дизайна (та же тема, что «Вариант 1»).
2. Товар крупным планом.
3. Условия акции: цена или скидка, текст, срок.
4. Как заказать: призыв, контакты, QR-код, логотип.

У всех слайдов одни цвета и шрифты — карусель выглядит единым рассказом.
Номер слайда и стрелка «→» подсказывают, что дальше есть продолжение.
"""

from PIL import Image, ImageDraw

from app.services import text
from app.services.design import DesignSpec
from app.services.templates import (
    CREAM,
    INK,
    MONTSERRAT,
    MONTSERRAT_SEMIBOLD,
    UNBOUNDED_BLACK,
    UNBOUNDED_BOLD,
    Content,
    brand_mark,
    drop_shadow,
    fit_product,
    make_qr,
    mix,
    render_template,
    text_in_box,
)

SIZE = (1080, 1350)  # 4:5 — самый крупный вертикальный формат ленты Instagram
SLIDES = 4


def slide_chrome(canvas: Image.Image, number: int, color: str) -> None:
    """Номер слайда «2/4» сверху справа и стрелка «→» снизу (кроме последнего слайда)."""
    w, h = canvas.size
    draw = ImageDraw.Draw(canvas)
    fnt = text.face_font(MONTSERRAT_SEMIBOLD, 30)
    draw.text((w - 60, 60), f"{number}/{SLIDES}", font=fnt, fill=color, anchor="ra")
    if number < SLIDES:
        arrow = text.face_font(UNBOUNDED_BOLD, 56)
        draw.text((w - 60, h - 60), "→", font=arrow, fill=color, anchor="rd")


def product_slide(c: Content) -> Image.Image:
    w, h = SIZE
    canvas = Image.new("RGBA", SIZE, CREAM)
    draw = ImageDraw.Draw(canvas)
    r = int(w * 0.46)
    draw.ellipse((w // 2 - r, h // 2 - r, w // 2 + r, h // 2 + r), fill=mix(c.primary, CREAM, 0.6))
    product, pos = fit_product(c.cutout, (int(w * 0.1), int(h * 0.14), int(w * 0.9), int(h * 0.86)))
    drop_shadow(canvas, product, pos, (0, 24), 30, 90)
    canvas.alpha_composite(product, pos)
    brand_mark(canvas, c, (60, 50, w // 2, 110), INK)
    slide_chrome(canvas, 2, INK)
    return canvas.convert("RGB")


def conditions_slide(c: Content) -> Image.Image:
    w, h = SIZE
    canvas = Image.new("RGBA", SIZE, c.primary)
    ink = text.readable_text_color(c.primary)
    m = 80
    y = 160
    if c.discount:
        y = text_in_box(canvas, c.discount, (m, y, w - m, y + 300), UNBOUNDED_BLACK, ink, 260, 60)
        y += 30
    if c.old_price:
        fnt = text.face_font(MONTSERRAT_SEMIBOLD, 48)
        label = f"вместо {c.old_price}"
        draw = ImageDraw.Draw(canvas)
        draw.text((m, y), label, font=fnt, fill=ink)
        start = m + text.text_width("вместо ", fnt)
        mid = y + fnt.getbbox(label)[3] * 0.6
        draw.line((start, mid, m + text.text_width(label, fnt), mid), fill=c.secondary, width=5)
        y += 90
    bottom = h - 260 if c.deadline else h - 160
    text_in_box(canvas, c.full_text, (m, y + 20, w - m, bottom), c.face(MONTSERRAT), ink, 88, 30)
    if c.deadline:
        pill_h = 90
        fnt, _ = text.fit_text(c.deadline, w - 2 * m, 50, 50, 20, UNBOUNDED_BOLD)
        pill_w = int(text.text_width(c.deadline, fnt) + pill_h)
        draw = ImageDraw.Draw(canvas)
        draw.rounded_rectangle(
            (m, h - 220, m + pill_w, h - 220 + pill_h), radius=pill_h // 2, fill=c.secondary
        )
        draw.text(
            (m + pill_w / 2, h - 220 + pill_h / 2),
            c.deadline,
            font=fnt,
            fill=text.readable_text_color(c.secondary),
            anchor="mm",
        )
    slide_chrome(canvas, 3, ink)
    return canvas.convert("RGB")


def contacts_slide(c: Content) -> Image.Image:
    w, h = SIZE
    canvas = Image.new("RGBA", SIZE, INK)
    m = 80
    draw = ImageDraw.Draw(canvas)
    cta = c.cta or "Ждём вас!"
    y = text_in_box(canvas, cta, (m, 160, w - m, 460), UNBOUNDED_BLACK, "#FFFFFF", 150, 40)
    draw.rectangle((m, y + 40, m + 160, y + 52), fill=c.secondary)
    y += 100
    if c.contacts:
        y = text_in_box(canvas, c.contacts, (m, y, w - m, y + 200), MONTSERRAT, "#FFFFFF", 64, 26)
        y += 60
    if c.qr_url:
        qr_size = 380
        canvas.paste(make_qr(c.qr_url, qr_size), (m, min(y, h - qr_size - 200)))
        hint = text.face_font(MONTSERRAT_SEMIBOLD, 32)
        draw.text(
            (m + qr_size + 40, min(y, h - qr_size - 200) + qr_size // 2),
            "Наведите\nкамеру",
            font=hint,
            fill="#FFFFFF",
            anchor="lm",
        )
    brand_mark(canvas, c, (m, h - 150, w // 2, h - 80), "#FFFFFF")
    slide_chrome(canvas, 4, "#FFFFFF")
    return canvas.convert("RGB")


def render_carousel(spec: DesignSpec, content: Content) -> list[Image.Image]:
    """4 слайда карусели в стиле дизайн-задания spec."""
    cover = render_template(spec.template, content, SIZE)
    canvas = cover.convert("RGBA")
    slide_chrome(canvas, 1, text.readable_text_color(hex_of_corner(cover)))
    return [
        canvas.convert("RGB"),
        product_slide(content),
        conditions_slide(content),
        contacts_slide(content),
    ]


def hex_of_corner(image: Image.Image) -> str:
    """Цвет правого верхнего угла — чтобы номер слайда был виден на любой обложке."""
    r, g, b = image.convert("RGB").getpixel((image.width - 60, 60))
    return f"#{r:02X}{g:02X}{b:02X}"

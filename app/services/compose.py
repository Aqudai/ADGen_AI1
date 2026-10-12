"""Шаг 3 пайплайна: композиция — товар без фона ставится на сцену с тенью."""

from PIL import Image, ImageDraw, ImageFilter, ImageOps

Box = tuple[int, int, int, int]  # (left, top, right, bottom) в пикселях


def cover(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    """Растягивает сцену на весь баннер с сохранением пропорций и обрезает лишнее по краям."""
    return ImageOps.fit(image.convert("RGB"), size, Image.LANCZOS)


def crop_to_content(cutout: Image.Image) -> Image.Image:
    """Обрезает прозрачные поля вокруг товара."""
    # Порог 10 — игнорируем почти прозрачную «пыль» по краям маски
    bbox = cutout.getchannel("A").point(lambda a: 255 if a > 10 else 0).getbbox()
    return cutout.crop(bbox) if bbox else cutout


def place_product(canvas: Image.Image, cutout: Image.Image, box: Box) -> None:
    """Вписывает товар в box и ставит его на нижнюю границу box, с тенью.

    Тень из двух слоёв:
    - контактная: тёмный размытый эллипс под основанием — товар «стоит», а не висит;
    - мягкий ореол из силуэта товара — отделяет товар от фона.
    """
    product = crop_to_content(cutout.convert("RGBA"))
    left, top, right, bottom = box
    scale = min((right - left) / product.width, (bottom - top) / product.height)
    width, height = max(1, int(product.width * scale)), max(1, int(product.height * scale))
    product = product.resize((width, height), Image.LANCZOS)
    x = left + (right - left - width) // 2
    y = bottom - height

    shadow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    ellipse_h = max(8, width // 12)
    ImageDraw.Draw(shadow).ellipse(
        (
            x + width * 0.08,
            y + height - ellipse_h // 2,
            x + width * 0.92,
            y + height + ellipse_h // 2,
        ),
        fill=(0, 0, 0, 120),
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(max(4, width // 25)))

    silhouette = Image.new("RGBA", product.size, (0, 0, 0, 0))
    silhouette.putalpha(product.getchannel("A").point(lambda a: a * 60 // 255))
    halo = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    halo.paste(silhouette, (x, y + max(2, height // 60)))
    halo = halo.filter(ImageFilter.GaussianBlur(max(6, width // 18)))

    canvas.alpha_composite(halo)
    canvas.alpha_composite(shadow)
    canvas.alpha_composite(product, (x, y))


def place_logo(canvas: Image.Image, logo: Image.Image, box: Box) -> None:
    """Вписывает логотип в box (по левому краю). Логотипу без прозрачности
    подкладываем белую скруглённую плашку — иначе он выглядит «наклейкой»."""
    left, top, right, bottom = box
    logo = logo.convert("RGBA")
    has_transparency = logo.getchannel("A").getextrema()[0] < 250
    pad = 0 if has_transparency else max(6, (bottom - top) // 8)
    max_w, max_h = right - left - 2 * pad, bottom - top - 2 * pad
    scale = min(max_w / logo.width, max_h / logo.height)
    logo = logo.resize(
        (max(1, int(logo.width * scale)), max(1, int(logo.height * scale))), Image.LANCZOS
    )

    if not has_transparency:
        plate = (left, top, left + logo.width + 2 * pad, top + logo.height + 2 * pad)
        ImageDraw.Draw(canvas).rounded_rectangle(plate, radius=pad * 2, fill=(255, 255, 255, 235))
    canvas.alpha_composite(logo, (left + pad, top + pad))

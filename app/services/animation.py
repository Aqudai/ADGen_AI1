"""Видео-сторис: короткий MP4 из готового баннера-сторис.

Эффект «Кена Бёрнса» — плавное приближение кадра — и появление из затемнения в начале.
Такие видео Instagram принимает в сторис, а движение привлекает больше внимания,
чем статичная картинка. Кодек H.264 (библиотека PyAV), его воспроизводят все телефоны.
"""

import io

import av
from PIL import Image

FPS = 24
SECONDS = 5
ZOOM = 0.08  # к концу ролика кадр приближен на 8%
FADE_SECONDS = 0.5


def frames(image: Image.Image):
    """Кадры ролика: приближение к центру + затемнение в начале."""
    w, h = image.size
    total = FPS * SECONDS
    black = Image.new("RGB", (w, h), "black")
    for i in range(total):
        progress = i / (total - 1)
        # Плавное «замедление» к концу: ease-out
        scale = 1 + ZOOM * (1 - (1 - progress) ** 2)
        cw, ch = int(w / scale), int(h / scale)
        left, top = (w - cw) // 2, (h - ch) // 2
        frame = image.crop((left, top, left + cw, top + ch)).resize((w, h), Image.BILINEAR)
        fade = min(1.0, i / (FPS * FADE_SECONDS))
        if fade < 1:
            frame = Image.blend(black, frame, fade)
        yield frame


def story_video(image: Image.Image) -> bytes:
    """MP4 (H.264) из картинки-сторис 1080×1920."""
    buffer = io.BytesIO()
    with av.open(buffer, mode="w", format="mp4") as container:
        stream = container.add_stream("libx264", rate=FPS)
        stream.width, stream.height = image.size
        stream.pix_fmt = "yuv420p"  # самый совместимый формат пикселей для телефонов
        stream.options = {"crf": "23", "preset": "veryfast"}
        for frame in frames(image.convert("RGB")):
            for packet in stream.encode(av.VideoFrame.from_image(frame)):
                container.mux(packet)
        for packet in stream.encode():  # дописываем то, что осталось в кодеке
            container.mux(packet)
    return buffer.getvalue()

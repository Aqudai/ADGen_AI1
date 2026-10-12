"""Справочники: стили фона, форматы и варианты оформления баннеров."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Style:
    key: str
    label: str
    description: str
    # Описание сцены для нейросети. На английском: модели генерации понимают его лучше.
    # Описываем пустую сцену («nothing on the table»): товар и текст добавим сами.
    prompt: str
    # Цвет плашки и бейджа скидки (в Спринте 3 заменится фирменным цветом из профиля бренда)
    accent: str


@dataclass(frozen=True)
class BannerFormat:
    key: str
    label: str
    width: int
    height: int
    # Варианты оформления этого формата (ключи VARIANTS)
    variants: tuple[str, ...] = ("overlay", "panel")

    @property
    def size(self) -> tuple[int, int]:
        return (self.width, self.height)

    @property
    def title(self) -> str:
        return f"{self.label} {self.width}×{self.height}"


STYLES = {
    "cozy": Style(
        key="cozy",
        label="Уютный",
        description="Тёплый свет, дерево, атмосфера кофейни",
        prompt=(
            "empty rustic wooden table in the foreground, cozy coffee shop interior in the "
            "background, warm soft window light, warm bokeh lights, shallow depth of field, "
            "nothing on the table, professional product photography backdrop, photorealistic"
        ),
        accent="#E8743B",
    ),
    "festive": Style(
        key="festive",
        label="Праздничный",
        description="Огоньки, конфетти, яркие цвета",
        prompt=(
            "empty table surface in the foreground, festive celebration background, golden "
            "bokeh lights, confetti, garland, rich red and gold colors, shallow depth of field, "
            "nothing on the table, professional product photography backdrop, photorealistic"
        ),
        accent="#E11D74",
    ),
    "minimal": Style(
        key="minimal",
        label="Минимализм",
        description="Чистый светлый фон, мягкие тени",
        prompt=(
            "minimalist studio backdrop, empty smooth pastel beige surface and wall, soft "
            "natural light, gentle shadows, clean empty space, professional product "
            "photography backdrop, photorealistic"
        ),
        accent="#1F2937",
    ),
}

FORMATS = {
    "post": BannerFormat("post", "Пост", 1080, 1080),
    "story": BannerFormat("story", "Сторис", 1080, 1920),
    # Фото для блока «Скидки» в карточке 2GIS. По требованиям 2GIS на этом фото нельзя
    # размещать текст и логотипы (текст акции вводится в поля карточки), минимум 600×312.
    # Берём вдвое больше с той же пропорцией 25:13. Подробно — docs/ARCHITECTURE.md.
    "2gis": BannerFormat("2gis", "2GIS", 1200, 624, variants=("clean",)),
}

VARIANTS = {
    "overlay": "Текст на фоне",
    "panel": "Текст на плашке",
    "clean": "Без текста, для блока «Скидки»",
}

MAX_PROMO_LENGTH = 120
TWOGIS_TITLE_LIMIT = 45  # длина заголовка скидки в карточке 2GIS

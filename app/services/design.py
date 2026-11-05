"""Понимание запроса «каким вы видите баннер» — без нейросети, по ключевым словам.

Пользователь пишет обычным текстом: «уютно, по-осеннему, шрифт с засечками» или
«ярко и дерзко, неон». Мы ищем в запросе (и в тексте акции) знакомые слова и превращаем
их в «дизайн-задания» — 3–4 разных варианта: какой шаблон, какие цвета, какой шрифт.

Почему не нейросеть: бесплатно, работает без интернета и предсказуемо — решение можно
объяснить: в таблицах ниже видно, какое слово к чему приводит. Если подключить языковую
модель, она будет выдавать такие же дизайн-задания (DesignSpec) — остальной код не изменится.
"""

import re
from dataclasses import asdict, dataclass, field

from app.services.presets import DEFAULT_PRIMARY, DEFAULT_SECONDARY


@dataclass(frozen=True)
class Mood:
    key: str
    label: str
    words: tuple[str, ...]  # начала слов: «уют» найдёт «уютно», «уютный», «уюта»
    templates: tuple[str, ...]  # подходящие шаблоны, по порядку
    palettes: tuple[tuple[str, str], ...]  # пары (основной цвет, второй цвет)
    scene_style: str  # описание сцены для нейросети (ключ STYLES), если она подключена


MOODS = (
    Mood(
        "cozy",
        "уютное",
        (
            "уют",
            "тепл",
            "тёпл",
            "осен",
            "кофе",
            "кофейн",
            "выпеч",
            "домашн",
            "какао",
            "зим",
            "плед",
            "пекар",
        ),
        ("arch", "editorial", "photo", "pattern"),
        (("#7C4A2D", "#E9B44C"), ("#9A3412", "#FCD34D"), ("#5B4636", "#D97757")),
        "cozy",
    ),
    Mood(
        "bright",
        "яркое",
        (
            "ярк",
            "дерз",
            "сочн",
            "неон",
            "кислот",
            "молодеж",
            "молодёж",
            "энерг",
            "лет",
            "распрод",
            "громк",
        ),
        ("pop", "poster", "pattern", "split"),
        (("#E8552B", "#1E3A8A"), ("#7C3AED", "#FACC15"), ("#DB2777", "#22D3EE")),
        "festive",
    ),
    Mood(
        "premium",
        "премиальное",
        (
            "преми",
            "люкс",
            "дорог",
            "элегант",
            "роскош",
            "салон",
            "ювелир",
            "спа",
            "вечерн",
            "золот",
            "стильн",
        ),
        ("luxe", "editorial", "split", "arch"),
        (("#111111", "#D6B26E"), ("#1F2937", "#C9A96E"), ("#3F1D2B", "#E7C59A")),
        "minimal",
    ),
    Mood(
        "minimal",
        "минималистичное",
        ("минимал", "прост", "чист", "светл", "нежн", "строг", "скандинав", "воздуш", "пастел"),
        ("arch", "editorial", "split", "photo"),
        (("#94A3B8", "#1E293B"), ("#D6C3A5", "#3F3F46"), ("#A7C4BC", "#2F3E46")),
        "minimal",
    ),
    Mood(
        "festive",
        "праздничное",
        (
            "праздн",
            "новый год",
            "новогод",
            "рожден",
            "8 марта",
            "наурыз",
            "подар",
            "ёлк",
            "елк",
            "салют",
        ),
        ("pattern", "pop", "poster", "luxe"),
        (("#B91C1C", "#FACC15"), ("#14532D", "#FBBF24"), ("#1E3A8A", "#F472B6")),
        "festive",
    ),
    Mood(
        "fresh",
        "свежее, природное",
        (
            "эко",
            "натурал",
            "свеж",
            "зелен",
            "зелён",
            "органи",
            "цвет",
            "флорист",
            "растен",
            "фрукт",
            "овощ",
            "весн",
        ),
        ("pattern", "arch", "photo", "editorial"),
        (("#15803D", "#FDE68A"), ("#0F766E", "#FCA5A5"), ("#4D7C0F", "#FEF3C7")),
        "minimal",
    ),
)
DEFAULT_MOOD = MOODS[1]  # если в запросе нет знакомых слов — яркие варианты, их лучше видно в ленте

# Названия цветов → цвет. Ищем начало слова: «синий», «синего», «синие»
COLOR_WORDS = {
    "красн": "#DC2626",
    "алый": "#E11D48",
    "оранж": "#EA580C",
    "желт": "#EAB308",
    "жёлт": "#EAB308",
    "зелен": "#16A34A",
    "зелён": "#16A34A",
    "мят": "#2DD4BF",
    "бирюз": "#0D9488",
    "голуб": "#38BDF8",
    "син": "#1D4ED8",
    "фиолет": "#7C3AED",
    "сирен": "#A78BFA",
    "розов": "#EC4899",
    "малин": "#BE185D",
    "бордо": "#7F1D1D",
    "коричн": "#78350F",
    "беж": "#D6C3A5",
    "черн": "#111111",
    "чёрн": "#111111",
    "сер": "#6B7280",
    "золот": "#D6B26E",
    "неон": "#A3E635",
    "персик": "#FDBA74",
}

# Шрифт заголовка
FONT_WORDS = {
    "serif": ("засеч", "классич", "антикв", "журнал", "книжн", "винтаж", "ретро"),
    "condensed": ("узк", "плакат", "постер", "спорт", "мощн"),
    "rounded": ("округл", "мягк", "детск", "игрив", "весел", "весёл"),
}
FONT_LABELS = {"serif": "с засечками", "condensed": "узкий плакатный", "rounded": "округлый"}

ALL_TEMPLATES = ("pop", "photo", "luxe", "arch", "split", "pattern", "editorial", "poster")
VARIANT_COUNT = 4


@dataclass(frozen=True)
class DesignSpec:
    """Одно дизайн-задание: по нему шаблон рисует вариант баннера."""

    template: str
    primary: str
    secondary: str
    font: str | None = None  # serif / condensed / rounded — или шрифт шаблона по умолчанию


@dataclass
class Interpretation:
    """Как мы поняли запрос — показываем пользователю, чтобы было видно «почему так»."""

    mood: str
    mood_label: str
    colors: list[str] = field(default_factory=list)
    font: str | None = None
    matched: list[str] = field(default_factory=list)  # какие слова узнали
    variants: list[DesignSpec] = field(default_factory=list)
    scene_style: str = "cozy"

    def to_dict(self) -> dict:
        return asdict(self)


def find_words(text: str, stems) -> list[str]:
    """Слова из текста, которые начинаются с одной из основ («уют» → «уютно»)."""
    found = []
    for stem in stems:
        if " " in stem:  # фраза: «новый год»
            if stem in text:
                found.append(stem)
            continue
        match = re.search(rf"(?<!\w){re.escape(stem)}\w*", text)
        if match:
            found.append(match.group(0))
    return found


def interpret(request: str, promo_text: str = "", brand_colors: tuple[str, str] | None = None):
    """Запрос → Interpretation с VARIANT_COUNT разными дизайн-заданиями."""
    text = f"{request} {promo_text}".lower().replace("ё", "е")
    request_lower = request.lower().replace("ё", "е")

    # 1. Настроение: где больше совпадений. Запрос пользователя весит больше текста акции.
    best, best_score, matched = DEFAULT_MOOD, 0, []
    for mood in MOODS:
        stems = [w.replace("ё", "е") for w in mood.words]
        score = 2 * len(find_words(request_lower, stems)) + len(find_words(text, stems))
        if score > best_score:
            best, best_score, matched = mood, score, find_words(text, stems)

    # 2. Цвета, названные в запросе (только в запросе: «синий» в тексте акции — не пожелание)
    colors, color_words = [], []
    for stem, value in COLOR_WORDS.items():
        words = find_words(request_lower, [stem.replace("ё", "е")])
        if words and value not in colors:
            colors.append(value)
            color_words += words

    # 3. Шрифт
    font = None
    for key, stems in FONT_WORDS.items():
        words = find_words(request_lower, [s.replace("ё", "е") for s in stems])
        if words:
            font, matched = key, matched + words
            break

    # 4. Палитры: названные цвета → цвета профиля бренда → палитры настроения
    if len(colors) >= 2:
        palettes = [(colors[0], colors[1])]
    elif colors:
        palettes = [(colors[0], p[1]) for p in best.palettes]
    elif brand_colors and brand_colors != (DEFAULT_PRIMARY, DEFAULT_SECONDARY):
        palettes = [brand_colors] + list(best.palettes)
    else:
        palettes = list(best.palettes)

    # 5. Варианты: шаблоны настроения + один «неожиданный», чтобы было из чего выбрать
    templates = list(best.templates[: VARIANT_COUNT - 1])
    templates.append(next(t for t in ALL_TEMPLATES if t not in templates))
    variants = [
        DesignSpec(template, *palettes[i % len(palettes)], font=font)
        for i, template in enumerate(templates)
    ]

    return Interpretation(
        mood=best.key,
        mood_label=best.label,
        colors=colors,
        font=font,
        matched=list(dict.fromkeys(matched + color_words)),
        variants=variants,
        scene_style=best.scene_style,
    )

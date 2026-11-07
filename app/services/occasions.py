"""Календарь поводов для акций (Казахстан): подсказываем на странице создания баннера,
что скоро праздник, и предлагаем готовые текст и пожелание к дизайну."""

from dataclasses import dataclass
from datetime import date, timedelta


@dataclass(frozen=True)
class Occasion:
    name: str
    day: date
    promo_text: str
    design_request: str

    def days_left(self, today: date) -> int:
        return (self.day - today).days


def black_friday(year: int) -> date:
    """Чёрная пятница — четвёртая пятница ноября."""
    first = date(year, 11, 1)
    first_friday = first + timedelta(days=(4 - first.weekday()) % 7)
    return first_friday + timedelta(weeks=3)


def occasions_for(year: int) -> list[Occasion]:
    return [
        Occasion(
            "Новый год",
            date(year, 1, 1),
            "Новогодняя скидка 20% на всё меню!",
            "Праздничный, новогодний",
        ),
        Occasion(
            "День влюблённых",
            date(year, 2, 14),
            "Второй десерт в подарок для пары",
            "Нежно, розовый",
        ),
        Occasion(
            "8 марта",
            date(year, 3, 8),
            "Скидка 15% всем девушкам 8 марта",
            "Нежно, праздничный, розовый",
        ),
        Occasion(
            "Наурыз",
            date(year, 3, 21),
            "Наурыз құтты болсын! Скидка 20% на праздничное меню",
            "Праздничный, зелёный и золотой",
        ),
        Occasion(
            "День защиты детей", date(year, 6, 1), "Детям — мороженое в подарок", "Ярко, весело"
        ),
        Occasion(
            "1 сентября",
            date(year, 9, 1),
            "Снова в школу: скидка 10% на всё",
            "Ярко, синий и жёлтый",
        ),
        Occasion(
            "День Республики",
            date(year, 10, 25),
            "Праздничная скидка 25% в День Республики",
            "Праздничный, голубой и золотой",
        ),
        Occasion(
            "Чёрная пятница",
            black_friday(year),
            "Чёрная пятница: −50% только один день!",
            "Премиум, чёрный с золотом",
        ),
        Occasion(
            "День Независимости",
            date(year, 12, 16),
            "Скидка 16% в честь Дня Независимости",
            "Праздничный, голубой и золотой",
        ),
        Occasion(
            "Новогодние подарки",
            date(year, 12, 20),
            "Подарочные сертификаты к Новому году",
            "Праздничный, новогодний",
        ),
    ]


def upcoming(today: date, within_days: int = 30) -> Occasion | None:
    """Ближайший повод в ближайшие within_days дней (учитывая переход через Новый год)."""
    candidates = occasions_for(today.year) + occasions_for(today.year + 1)
    soon = [o for o in candidates if 0 <= o.days_left(today) <= within_days]
    return min(soon, key=lambda o: o.day) if soon else None


# Готовые тексты акций — по клику подставляются в поле «Текст акции»
READY_TEXTS = [
    "Скидка 20% на весь кофе до пятницы",
    "Второй десерт в подарок",
    "Счастливые часы: −30% с 15:00 до 17:00",
    "Новинка недели — попробуйте первыми!",
    "Бесплатная доставка от 5000 ₸",
    "−15% на первый визит",
]

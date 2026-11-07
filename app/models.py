"""Модели базы данных.

Таблицы добавляются по спринтам, каждая — своей миграцией Alembic
(план схемы — в docs/ARCHITECTURE.md).
"""

import uuid
from datetime import datetime
from enum import StrEnum
from pathlib import Path

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text, func
from sqlalchemy import false as sa_false
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.services.presets import DEFAULT_PRIMARY, DEFAULT_SECONDARY, FORMATS, VARIANTS
from app.services.storage import media_url
from app.services.templates import TEMPLATES


class User(Base):
    """Пользователь сервиса."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    brand: Mapped["BrandProfile | None"] = relationship(back_populates="user")


class BrandProfile(Base):
    """Профиль бренда: название, логотип и фирменные цвета — подставляются в баннеры."""

    __tablename__ = "brand_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    business_name: Mapped[str] = mapped_column(String(80), default="")
    logo_path: Mapped[str | None] = mapped_column(String(255))
    primary_color: Mapped[str] = mapped_column(String(7), default=DEFAULT_PRIMARY)
    secondary_color: Mapped[str] = mapped_column(String(7), default=DEFAULT_SECONDARY)
    contacts: Mapped[str | None] = mapped_column(String(100))  # телефон, Instagram — на баннер
    qr_url: Mapped[str | None] = mapped_column(String(300))  # ссылка для QR-кода на баннере

    user: Mapped[User] = relationship(back_populates="brand")

    @property
    def logo_url(self) -> str | None:
        return media_url(self.logo_path) if self.logo_path else None


class GenerationStatus(StrEnum):
    """Этапы жизни генерации. Храним строкой, чтобы легко добавлять новые этапы."""

    PENDING = "pending"  # в очереди, воркер ещё не взял
    PROCESSING = "processing"  # воркер обрабатывает
    DONE = "done"  # готово
    FAILED = "failed"  # ошибка, текст в error_message


class GenerationStep(StrEnum):
    """Шаг пайплайна, который сейчас выполняет воркер (для индикатора прогресса)."""

    CUTOUT = "cutout"  # удаление фона
    SCENE = "scene"  # генерация сцены
    COMPOSE = "compose"  # сборка баннеров


class SceneSource(StrEnum):
    AI = "ai"  # нарисовала нейросеть
    FALLBACK = "fallback"  # запасной фон (только у генераций Спринта 2)


class Generation(Base):
    """Одна генерация: исходное фото, параметры баннеров и результаты.

    id — UUID, а не 1, 2, 3: адрес страницы и файлов нельзя подобрать перебором.
    """

    __tablename__ = "generations"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    # Пустое у генераций Спринтов 1–2 (до регистрации)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[str] = mapped_column(String(20), default=GenerationStatus.PENDING)
    step: Mapped[str | None] = mapped_column(String(20))

    # Что заказал пользователь. Пустые только у генераций Спринта 1 (там было лишь удаление фона).
    promo_text: Mapped[str | None] = mapped_column(Text)
    style: Mapped[str | None] = mapped_column(String(20))  # только у генераций Спринтов 2–3
    formats: Mapped[list[str] | None] = mapped_column(JSON)
    # Пожелание пользователя («уютно, по-осеннему») и как мы его поняли (design.interpret)
    design_request: Mapped[str | None] = mapped_column(Text)
    design: Mapped[dict | None] = mapped_column(JSON)
    # Дополнительное содержание баннера (всё необязательно)
    text_kz: Mapped[str | None] = mapped_column(Text)
    price: Mapped[str | None] = mapped_column(String(30))
    old_price: Mapped[str | None] = mapped_column(String(30))
    deadline: Mapped[str | None] = mapped_column(String(60))
    cta: Mapped[str | None] = mapped_column(String(40))
    contacts: Mapped[str | None] = mapped_column(String(100))  # снимок из профиля бренда
    qr_url: Mapped[str | None] = mapped_column(String(300))  # снимок из профиля бренда

    # «Ещё варианты» / «Другие цвета» / «Изменить» создают новую генерацию от этой (родителя)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("generations.id", ondelete="SET NULL")
    )
    template_shift: Mapped[int] = mapped_column(default=0, server_default="0")
    palette_shift: Mapped[int] = mapped_column(default=0, server_default="0")
    # Секретная ссылка «поделиться»: /s/<share_token> открывается без входа
    share_token: Mapped[str | None] = mapped_column(String(32), unique=True)
    # Снимок профиля бренда на момент генерации: если профиль потом поменяют,
    # старые баннеры в истории останутся такими, какими были сделаны
    brand_name: Mapped[str | None] = mapped_column(String(80))
    primary_color: Mapped[str | None] = mapped_column(String(7))
    secondary_color: Mapped[str | None] = mapped_column(String(7))

    # Пути к файлам относительно папки media/
    source_path: Mapped[str] = mapped_column(String(255))
    logo_path: Mapped[str | None] = mapped_column(String(255))
    cutout_path: Mapped[str | None] = mapped_column(String(255))
    scene_path: Mapped[str | None] = mapped_column(String(255))

    scene_source: Mapped[str | None] = mapped_column(String(20))
    # Почему фон нарисован без нейросети (нет ключа, нет кредитов...) — показываем пользователю
    scene_note: Mapped[str | None] = mapped_column(Text)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    banners: Mapped[list["Banner"]] = relationship(
        back_populates="generation", cascade="all, delete-orphan", order_by="Banner.id"
    )

    @property
    def source_url(self) -> str:
        return media_url(self.source_path)

    @property
    def cutout_url(self) -> str | None:
        return media_url(self.cutout_path) if self.cutout_path else None

    @property
    def in_progress(self) -> bool:
        return self.status in (GenerationStatus.PENDING, GenerationStatus.PROCESSING)

    @property
    def preview_url(self) -> str:
        """Картинка для списка истории: первый баннер, иначе исходное фото."""
        return self.banners[0].image_url if self.banners else self.source_url

    def banners_by_variant(self) -> list[tuple[str, str, list["Banner"]]]:
        """Баннеры по вариантам: [("pop-1", "Вариант 1 · Яркий", [пост, сторис, 2GIS]), ...]."""
        groups: dict[str, list[Banner]] = {}
        for banner in self.banners:
            groups.setdefault(banner.variant, []).append(banner)
        return [
            (variant, f"Вариант {i} · {items[0].variant_label}", items)
            for i, (variant, items) in enumerate(groups.items(), start=1)
        ]


class Banner(Base):
    """Готовый баннер одного формата и варианта оформления."""

    __tablename__ = "banners"

    id: Mapped[int] = mapped_column(primary_key=True)
    generation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("generations.id", ondelete="CASCADE"), index=True
    )
    format: Mapped[str] = mapped_column(String(20))
    variant: Mapped[str] = mapped_column(String(20))
    image_path: Mapped[str] = mapped_column(String(255))
    favorite: Mapped[bool] = mapped_column(default=False, server_default=sa_false())

    generation: Mapped[Generation] = relationship(back_populates="banners")

    @property
    def image_url(self) -> str:
        return media_url(self.image_path)

    @property
    def variant_label(self) -> str:
        # Новые варианты называются по шаблону: «pop-1» → «Яркий»
        template = TEMPLATES.get(self.variant.split("-")[0])
        return template.label if template else VARIANTS.get(self.variant, self.variant)

    @property
    def format_title(self) -> str:
        if self.format == "carousel":  # carousel-2.jpg → «Слайд 2 из 4»
            return f"Слайд {Path(self.image_path).stem.split('-')[-1]} из 4"
        return FORMATS[self.format].title

    @property
    def download_name(self) -> str:
        # Имя файла уникально в генерации: «pop-1-post» → adgen-pop-1-post.jpg
        return f"adgen-{Path(self.image_path).stem}.jpg"

    @property
    def aspect_ratio(self) -> str:
        """Для CSS aspect-ratio: карточка в галерее сразу нужной формы."""
        fmt = FORMATS[self.format]
        return f"{fmt.width} / {fmt.height}"

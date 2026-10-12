"""Модели базы данных.

Таблицы добавляются по спринтам, каждая — своей миграцией Alembic
(план схемы — в docs/ARCHITECTURE.md).
"""

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.services.presets import DEFAULT_PRIMARY, DEFAULT_SECONDARY, FORMATS, STYLES, VARIANTS
from app.services.storage import media_url


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
    FALLBACK = "fallback"  # запасной фон, нарисованный программно


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
    style: Mapped[str | None] = mapped_column(String(20))
    formats: Mapped[list[str] | None] = mapped_column(JSON)
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

    @property
    def style_label(self) -> str | None:
        return STYLES[self.style].label if self.style in STYLES else None

    def banners_by_format(self) -> list[tuple[str, list["Banner"]]]:
        """Баннеры по форматам в порядке выбора: [("Пост 1080×1080", [...]), ...]."""
        groups: dict[str, list[Banner]] = {}
        for banner in self.banners:
            groups.setdefault(banner.format, []).append(banner)
        return [(FORMATS[key].title, items) for key, items in groups.items()]


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

    generation: Mapped[Generation] = relationship(back_populates="banners")

    @property
    def image_url(self) -> str:
        return media_url(self.image_path)

    @property
    def variant_label(self) -> str:
        return VARIANTS.get(self.variant, self.variant)

    @property
    def download_name(self) -> str:
        return f"adgen-{self.format}-{self.variant}.jpg"

    @property
    def aspect_ratio(self) -> str:
        """Для CSS aspect-ratio: карточка в галерее сразу нужной формы."""
        fmt = FORMATS[self.format]
        return f"{fmt.width} / {fmt.height}"

"""Модели базы данных.

Таблицы добавляются по спринтам, каждая — своей миграцией Alembic
(план схемы — в docs/ARCHITECTURE.md).
"""

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.services.storage import media_url


class User(Base):
    """Пользователь сервиса. Регистрация и вход появятся в Спринте 3."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class GenerationStatus(StrEnum):
    """Этапы жизни генерации. Храним строкой, чтобы легко добавлять новые этапы."""

    PENDING = "pending"  # в очереди, воркер ещё не взял
    PROCESSING = "processing"  # воркер обрабатывает
    DONE = "done"  # готово
    FAILED = "failed"  # ошибка, текст в error_message


class Generation(Base):
    """Одна обработка фото: исходник и результаты.

    id — UUID, а не 1, 2, 3: адрес страницы и файлов нельзя подобрать перебором.
    """

    __tablename__ = "generations"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    # До Спринта 3 (регистрация) генерации анонимные, поэтому поле может быть пустым
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[str] = mapped_column(String(20), default=GenerationStatus.PENDING)
    # Пути к файлам относительно папки media/
    source_path: Mapped[str] = mapped_column(String(255))
    cutout_path: Mapped[str | None] = mapped_column(String(255))
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    @property
    def source_url(self) -> str:
        return media_url(self.source_path)

    @property
    def cutout_url(self) -> str | None:
        return media_url(self.cutout_path) if self.cutout_path else None

    @property
    def in_progress(self) -> bool:
        return self.status in (GenerationStatus.PENDING, GenerationStatus.PROCESSING)

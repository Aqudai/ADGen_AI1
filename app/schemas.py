"""Pydantic-схемы: проверка данных формы и ответы JSON API."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, ValidationError, field_validator

from app.services.presets import FORMATS, MAX_PROMO_LENGTH, STYLES


class BannerRequest(BaseModel):
    """Параметры баннеров из формы. Сообщения об ошибках — для пользователя, поэтому по-русски."""

    promo_text: str
    style: str
    formats: list[str]

    @field_validator("promo_text")
    @classmethod
    def check_promo_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Введите текст акции.")
        if len(value) > MAX_PROMO_LENGTH:
            raise ValueError(f"Текст акции длиннее {MAX_PROMO_LENGTH} символов — сократите его.")
        return value

    @field_validator("style")
    @classmethod
    def check_style(cls, value: str) -> str:
        if value not in STYLES:
            raise ValueError("Выберите стиль фона.")
        return value

    @field_validator("formats")
    @classmethod
    def check_formats(cls, value: list[str]) -> list[str]:
        value = list(dict.fromkeys(value))  # убираем повторы, порядок сохраняем
        if not value:
            raise ValueError("Выберите хотя бы один формат.")
        if any(key not in FORMATS for key in value):
            raise ValueError("Неизвестный формат баннера.")
        return value


def first_error(exc: ValidationError) -> str:
    """Текст первой ошибки без технической приставки «Value error, »."""
    error = exc.errors()[0]
    ctx_error = error.get("ctx", {}).get("error")
    return str(ctx_error) if ctx_error else error["msg"]


class BannerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    format: str
    variant: str
    image_url: str


class GenerationOut(BaseModel):
    # from_attributes — можно собрать схему прямо из объекта SQLAlchemy
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: str
    step: str | None
    promo_text: str | None
    style: str | None
    formats: list[str] | None
    source_url: str
    cutout_url: str | None
    scene_source: str | None
    scene_note: str | None
    error_message: str | None
    banners: list[BannerOut]
    created_at: datetime

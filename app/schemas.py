"""Pydantic-схемы: проверка данных формы и ответы JSON API."""

import re
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, ValidationError, field_validator, model_validator

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


EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")


class RegisterForm(BaseModel):
    email: str
    password: str
    password_confirm: str

    @field_validator("email")
    @classmethod
    def check_email(cls, value: str) -> str:
        value = value.strip().lower()
        if not EMAIL_RE.match(value) or len(value) > 255:
            raise ValueError("Введите корректный email.")
        return value

    @field_validator("password")
    @classmethod
    def check_password(cls, value: str) -> str:
        if len(value) < 8:
            raise ValueError("Пароль должен быть не короче 8 символов.")
        if len(value) > 128:
            raise ValueError("Пароль слишком длинный.")
        return value

    @model_validator(mode="after")
    def check_passwords_match(self):
        if self.password != self.password_confirm:
            raise ValueError("Пароли не совпадают.")
        return self


class BrandForm(BaseModel):
    business_name: str
    primary_color: str
    secondary_color: str

    @field_validator("business_name")
    @classmethod
    def check_name(cls, value: str) -> str:
        value = value.strip()
        if len(value) > 40:
            raise ValueError("Название бизнеса — не длиннее 40 символов.")
        return value

    @field_validator("primary_color", "secondary_color")
    @classmethod
    def check_color(cls, value: str) -> str:
        if not COLOR_RE.match(value):
            raise ValueError("Цвет должен быть в формате #RRGGBB.")
        return value.upper()


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

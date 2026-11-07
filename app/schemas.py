"""Pydantic-схемы: проверка данных формы и ответы JSON API."""

import re
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, ValidationError, field_validator, model_validator

from app.services.presets import FORMATS, MAX_DESIGN_REQUEST_LENGTH, MAX_PROMO_LENGTH

NBSP = "\u00a0"  # неразрывный пробел: «3 990 ₸» не разорвётся по строкам


def normalize_price(value: str) -> str | None:
    """«3990» → «3 990 ₸»; текст с валютой («$5», «990 руб») оставляем как есть."""
    value = value.strip()
    if not value:
        return None
    digits = value.replace(" ", "").replace(NBSP, "")
    if digits.isdigit():
        value = f"{int(digits):,}".replace(",", " ") + " ₸"
    return value.replace(" ", NBSP)


def short_text(value: str, limit: int, what: str) -> str | None:
    value = value.strip()
    if len(value) > limit:
        raise ValueError(f"{what} — не длиннее {limit} символов.")
    return value or None


class BannerRequest(BaseModel):
    """Параметры баннеров из формы. Сообщения об ошибках — для пользователя, поэтому по-русски."""

    # validate_default — проверять и значения по умолчанию: пустая строка превратится в None
    model_config = ConfigDict(validate_default=True)

    promo_text: str
    design_request: str = ""
    formats: list[str]
    text_kz: str | None = ""
    price: str | None = ""
    old_price: str | None = ""
    deadline: str | None = ""
    cta: str | None = ""

    @field_validator("text_kz")
    @classmethod
    def check_text_kz(cls, value: str) -> str | None:
        return short_text(value, MAX_PROMO_LENGTH, "Текст на казахском")

    @field_validator("price", "old_price")
    @classmethod
    def check_price(cls, value: str) -> str | None:
        short_text(value, 20, "Цена")
        return normalize_price(value)

    @field_validator("deadline")
    @classmethod
    def check_deadline(cls, value: str) -> str | None:
        return short_text(value, 40, "Срок акции")

    @field_validator("cta")
    @classmethod
    def check_cta(cls, value: str) -> str | None:
        return short_text(value, 30, "Призыв")

    @field_validator("promo_text")
    @classmethod
    def check_promo_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Введите текст акции.")
        if len(value) > MAX_PROMO_LENGTH:
            raise ValueError(f"Текст акции длиннее {MAX_PROMO_LENGTH} символов — сократите его.")
        return value

    @field_validator("design_request")
    @classmethod
    def check_design_request(cls, value: str) -> str:
        value = value.strip()
        if len(value) > MAX_DESIGN_REQUEST_LENGTH:
            raise ValueError(
                f"Пожелание к дизайну длиннее {MAX_DESIGN_REQUEST_LENGTH} символов — сократите его."
            )
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
    contacts: str = ""
    qr_url: str = ""

    @field_validator("contacts")
    @classmethod
    def check_contacts(cls, value: str) -> str | None:
        return short_text(value, 60, "Контакты")

    @field_validator("qr_url")
    @classmethod
    def check_qr_url(cls, value: str) -> str | None:
        """Ссылка для QR-кода. «instagram.com/cafe» → «https://instagram.com/cafe»."""
        value = value.strip()
        if not value:
            return None
        if not value.startswith(("http://", "https://")):
            value = "https://" + value
        if len(value) > 300 or " " in value or "." not in value:
            raise ValueError(
                "Ссылка для QR-кода выглядит неправильно — например: wa.me/77771234567"
            )
        return value

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
    design_request: str | None
    formats: list[str] | None
    source_url: str
    cutout_url: str | None
    scene_source: str | None
    scene_note: str | None
    error_message: str | None
    banners: list[BannerOut]
    created_at: datetime

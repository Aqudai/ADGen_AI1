"""Кабинет пользователя: профиль бренда и история генераций."""

import uuid
from typing import Annotated

from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import ValidationError
from sqlalchemy import select

from app.auth import CurrentUser
from app.db import DbSession
from app.models import BrandProfile, Generation
from app.schemas import BrandForm, first_error
from app.services import storage
from app.services.images import ImageValidationError, prepare_logo_image
from app.services.presets import DEFAULT_PRIMARY, DEFAULT_SECONDARY
from app.templating import templates

router = APIRouter()

MAX_LOGO_MB = 5
HISTORY_LIMIT = 50


def render_profile(request: Request, brand, status_code=200, **context):
    return templates.TemplateResponse(
        request,
        "profile.html",
        {"brand": brand, "max_logo_mb": MAX_LOGO_MB, **context},
        status_code=status_code,
    )


@router.get("/profile", response_class=HTMLResponse)
def profile_page(request: Request, user: CurrentUser, saved: bool = False, welcome: bool = False):
    brand = user.brand or BrandProfile(
        business_name="", primary_color=DEFAULT_PRIMARY, secondary_color=DEFAULT_SECONDARY
    )
    return render_profile(request, brand, saved=saved, welcome=welcome)


@router.post("/profile")
def save_profile(
    request: Request,
    user: CurrentUser,
    db: DbSession,
    business_name: Annotated[str, Form()] = "",
    primary_color: Annotated[str, Form()] = DEFAULT_PRIMARY,
    secondary_color: Annotated[str, Form()] = DEFAULT_SECONDARY,
    remove_logo: Annotated[bool, Form()] = False,
    logo: Annotated[UploadFile | None, File()] = None,
):
    brand = user.brand or BrandProfile(user_id=user.id)
    try:
        form = BrandForm(
            business_name=business_name,
            primary_color=primary_color,
            secondary_color=secondary_color,
        )
        logo_image = None
        if logo is not None and logo.filename:
            if logo.size is not None and logo.size > MAX_LOGO_MB * 1024 * 1024:
                raise ImageValidationError(f"Логотип больше {MAX_LOGO_MB} МБ.")
            logo_image = prepare_logo_image(logo.file)
    except (ValidationError, ImageValidationError) as exc:
        message = first_error(exc) if isinstance(exc, ValidationError) else str(exc)
        # Показываем форму с тем, что ввёл пользователь (в базу не сохраняем)
        entered = BrandProfile(
            business_name=business_name,
            primary_color=primary_color,
            secondary_color=secondary_color,
            logo_path=brand.logo_path,
        )
        return render_profile(request, entered, 400, error=message)

    brand.business_name = form.business_name
    brand.primary_color = form.primary_color
    brand.secondary_color = form.secondary_color
    if remove_logo:
        brand.logo_path = None
    if logo_image is not None:
        # Новое имя файла при каждой загрузке — браузер не покажет старый логотип из кеша
        brand.logo_path = f"brands/{user.id}/logo-{uuid.uuid4().hex[:8]}.png"
        storage.save_image(logo_image, brand.logo_path, format="PNG")
    db.add(brand)
    db.commit()
    return RedirectResponse("/profile?saved=1", status_code=303)


@router.get("/history", response_class=HTMLResponse)
def history_page(request: Request, user: CurrentUser, db: DbSession):
    generations = db.scalars(
        select(Generation)
        .where(Generation.user_id == user.id)
        .order_by(Generation.created_at.desc())
        .limit(HISTORY_LIMIT)
    ).all()
    return templates.TemplateResponse(request, "history.html", {"generations": generations})

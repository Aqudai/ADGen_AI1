"""Создание баннеров: форма, страница результата, статус для HTMX, архив для скачивания."""

import io
import uuid
import zipfile
from datetime import date
from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.auth import CurrentUser
from app.config import settings
from app.db import DbSession
from app.models import Generation, User
from app.schemas import BannerRequest, first_error
from app.services import storage
from app.services.images import ImageValidationError, prepare_source_image
from app.services.occasions import READY_TEXTS, upcoming
from app.services.presets import FORMATS, MAX_DESIGN_REQUEST_LENGTH, MAX_PROMO_LENGTH
from app.tasks import process_generation
from app.templating import templates

router = APIRouter()

EXTRA_FIELDS = ("text_kz", "price", "old_price", "deadline", "cta")
CTA_EXAMPLES = ["Закажите сейчас", "Ждём вас!", "Звоните", "Успейте купить"]

# Подсказки под полем «Каким вы видите баннер?» — по клику подставляются в поле
DESIGN_EXAMPLES = [
    "Уютно, по-осеннему, тёплые цвета",
    "Ярко и дерзко, неон",
    "Премиум, чёрный с золотом",
    "Минимализм, светлый, шрифт с засечками",
    "Праздничный, новогодний",
    "Свежо, натурально, зелёный",
]


def get_generation_or_404(db: Session, generation_id: uuid.UUID, user: User) -> Generation:
    """Генерация текущего пользователя. Чужая — тоже 404: не подсказываем, что она существует."""
    generation = db.get(Generation, generation_id)
    if generation is None or generation.user_id != user.id:
        raise HTTPException(status_code=404, detail="Генерация не найдена")
    return generation


def render_create_page(
    request: Request,
    user: User,
    error: str | None = None,
    form: dict | None = None,
    status_code: int = 200,
):
    # По умолчанию: уютный стиль и все форматы. При ошибке — то, что ввёл пользователь.
    form = form or {"promo_text": "", "design_request": "", "formats": list(FORMATS)}
    form = {field: "" for field in EXTRA_FIELDS} | form
    return templates.TemplateResponse(
        request,
        "create.html",
        {
            "error": error,
            "form": form,
            "design_examples": DESIGN_EXAMPLES,
            "ready_texts": READY_TEXTS,
            "occasion": upcoming(date.today()),
            "today": date.today(),
            "cta_examples": CTA_EXAMPLES,
            "max_design_request_length": MAX_DESIGN_REQUEST_LENGTH,
            "formats": FORMATS.values(),
            "max_upload_mb": settings.max_upload_mb,
            "brand": user.brand,
            "max_promo_length": MAX_PROMO_LENGTH,
        },
        status_code=status_code,
    )


def file_too_big(upload: UploadFile, max_mb: int) -> bool:
    return upload.size is not None and upload.size > max_mb * 1024 * 1024


@router.get("/create", response_class=HTMLResponse)
def create_page(request: Request, user: CurrentUser):
    return render_create_page(request, user)


@router.post("/generations")
def create_generation(
    request: Request,
    db: DbSession,
    user: CurrentUser,
    photo: Annotated[UploadFile | None, File()] = None,
    promo_text: Annotated[str, Form()] = "",
    design_request: Annotated[str, Form()] = "",
    text_kz: Annotated[str, Form()] = "",
    price: Annotated[str, Form()] = "",
    old_price: Annotated[str, Form()] = "",
    deadline: Annotated[str, Form()] = "",
    cta: Annotated[str, Form()] = "",
    formats: Annotated[list[str] | None, Form()] = None,
):
    """Принимает форму, сохраняет файлы и ставит генерацию в очередь Celery."""
    extra = {
        "text_kz": text_kz,
        "price": price,
        "old_price": old_price,
        "deadline": deadline,
        "cta": cta,
    }
    form = {"promo_text": promo_text, "design_request": design_request, "formats": formats or []}
    form |= extra

    def error(message: str):
        return render_create_page(request, user, message, form, status_code=400)

    try:
        params = BannerRequest(
            promo_text=promo_text, design_request=design_request, formats=formats or [], **extra
        )
    except ValidationError as exc:
        return error(first_error(exc))

    if photo is None or not photo.filename:
        return error("Выберите фото товара.")
    if file_too_big(photo, settings.max_upload_mb):
        return error(f"Фото больше {settings.max_upload_mb} МБ.")

    try:
        image = prepare_source_image(photo.file)
    except ImageValidationError as exc:
        return error(str(exc))

    generation = Generation(
        id=uuid.uuid4(),
        user_id=user.id,
        promo_text=params.promo_text,
        design_request=params.design_request or None,
        text_kz=params.text_kz,
        price=params.price,
        old_price=params.old_price,
        deadline=params.deadline,
        cta=params.cta,
        formats=params.formats,
    )
    generation.source_path = storage.generation_file(generation.id, "source.jpg")
    storage.save_image(image, generation.source_path, format="JPEG", quality=92)

    # Снимок профиля бренда: история не изменится, если профиль потом отредактируют
    if user.brand:
        generation.brand_name = user.brand.business_name or None
        generation.primary_color = user.brand.primary_color
        generation.secondary_color = user.brand.secondary_color
        generation.contacts = user.brand.contacts
        generation.qr_url = user.brand.qr_url
        if user.brand.logo_path:
            generation.logo_path = storage.generation_file(generation.id, "logo.png")
            storage.copy_file(user.brand.logo_path, generation.logo_path)

    db.add(generation)
    # Сначала сохраняем в базу, потом ставим задачу — иначе воркер может не найти запись
    db.commit()
    process_generation.delay(str(generation.id))

    # 303 — после POST браузер переходит на страницу результата обычным GET
    return RedirectResponse(f"/generations/{generation.id}", status_code=303)


@router.get("/generations/{generation_id}", response_class=HTMLResponse)
def generation_page(request: Request, generation_id: uuid.UUID, db: DbSession, user: CurrentUser):
    generation = get_generation_or_404(db, generation_id, user)
    return templates.TemplateResponse(request, "generation.html", {"generation": generation})


@router.get("/generations/{generation_id}/status", response_class=HTMLResponse)
def generation_status(request: Request, generation_id: uuid.UUID, db: DbSession, user: CurrentUser):
    """HTMX-фрагмент: прогресс, пока идёт обработка, затем галерея баннеров."""
    generation = get_generation_or_404(db, generation_id, user)
    return templates.TemplateResponse(
        request, "partials/generation_status.html", {"generation": generation}
    )


@router.get("/generations/{generation_id}/banners.zip")
def download_all(generation_id: uuid.UUID, db: DbSession, user: CurrentUser):
    """Все баннеры одним архивом."""
    generation = get_generation_or_404(db, generation_id, user)
    if not generation.banners:
        raise HTTPException(status_code=404, detail="Баннеры ещё не готовы")

    buffer = io.BytesIO()
    # JPEG уже сжат — в архиве храним без повторного сжатия (ZIP_STORED), так быстрее
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_STORED) as archive:
        for banner in generation.banners:
            archive.write(storage.media_path(banner.image_path), banner.download_name)
    return Response(
        buffer.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="adgen-banners.zip"'},
    )

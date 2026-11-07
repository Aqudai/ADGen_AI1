"""Создание баннеров: форма, страница результата, статус для HTMX, архив для скачивания."""

import io
import secrets
import uuid
import zipfile
from datetime import date
from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import CurrentUser
from app.config import settings
from app.db import DbSession
from app.models import Generation, User
from app.schemas import BannerRequest, first_error
from app.services import storage
from app.services.images import ImageValidationError, prepare_source_image
from app.services.limits import LIMIT_MESSAGE, limit_reached, used_today
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
    db: Session,
    user: User,
    error: str | None = None,
    form: dict | None = None,
    status_code: int = 200,
    parent: Generation | None = None,
):
    # По умолчанию: уютный стиль и все форматы. При ошибке — то, что ввёл пользователь.
    # Карусель и видео по умолчанию не отмечены: это дополнительные файлы и время
    default_formats = [key for key in FORMATS if key not in ("carousel", "video")]
    form = form or {"promo_text": "", "design_request": "", "formats": default_formats}
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
            "parent": parent,  # «Изменить»: фото берём из этой генерации
            "used_today": used_today(db, user),
            "user_is_pro": user.is_pro,
            "free_daily_limit": settings.free_daily_limit,
        },
        status_code=status_code,
    )


def file_too_big(upload: UploadFile, max_mb: int) -> bool:
    return upload.size is not None and upload.size > max_mb * 1024 * 1024


@router.get("/create", response_class=HTMLResponse)
def create_page(request: Request, user: CurrentUser, db: DbSession, edit: uuid.UUID | None = None):
    """Новая генерация. С ?edit=<id> — форма заполнена данными прошлой генерации, фото то же."""
    if edit is None:
        return render_create_page(request, db, user)
    parent = get_generation_or_404(db, edit, user)
    form = {"promo_text": parent.promo_text or "", "design_request": parent.design_request or ""}
    form["formats"] = parent.formats or list(FORMATS)
    form |= {field: getattr(parent, field) or "" for field in EXTRA_FIELDS}
    return render_create_page(request, db, user, form=form, parent=parent)


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
    parent_id: Annotated[uuid.UUID | None, Form()] = None,
):
    """Принимает форму, сохраняет файлы и ставит генерацию в очередь Celery."""
    parent = get_generation_or_404(db, parent_id, user) if parent_id else None
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
        return render_create_page(request, db, user, message, form, status_code=400, parent=parent)

    if limit_reached(db, user):
        return error(LIMIT_MESSAGE.format(limit=settings.free_daily_limit))

    try:
        params = BannerRequest(
            promo_text=promo_text, design_request=design_request, formats=formats or [], **extra
        )
    except ValidationError as exc:
        return error(first_error(exc))

    has_photo = photo is not None and bool(photo.filename)
    if not has_photo and parent is None:
        return error("Выберите фото товара.")
    image = None
    if has_photo:
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
        parent_id=parent.id if parent else None,
    )
    generation.source_path = storage.generation_file(generation.id, "source.jpg")
    if image is not None:
        storage.save_image(image, generation.source_path, format="JPEG", quality=92)
    else:
        copy_photo(parent, generation)  # «Изменить» без новой загрузки — фото и вырезка те же

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

    return enqueue(db, generation)


def enqueue(db: Session, generation: Generation) -> RedirectResponse:
    db.add(generation)
    # Сначала сохраняем в базу, потом ставим задачу — иначе воркер может не найти запись
    db.commit()
    process_generation.delay(str(generation.id))
    # 303 — после POST браузер переходит на страницу результата обычным GET
    return RedirectResponse(f"/generations/{generation.id}", status_code=303)


def copy_photo(parent: Generation, child: Generation) -> None:
    """Исходное фото и товар без фона — из родителя: удалять фон второй раз не нужно."""
    storage.copy_file(parent.source_path, child.source_path)
    if parent.cutout_path and storage.media_path(parent.cutout_path).exists():
        child.cutout_path = storage.generation_file(child.id, "cutout.png")
        storage.copy_file(parent.cutout_path, child.cutout_path)


COPIED_FIELDS = (
    "promo_text",
    "design_request",
    "formats",
    "text_kz",
    "price",
    "old_price",
    "deadline",
    "cta",
    "brand_name",
    "primary_color",
    "secondary_color",
    "contacts",
    "qr_url",
)


def variation_of(parent: Generation, template_shift: int, palette_shift: int) -> Generation:
    """Копия генерации с теми же данными, но другими темами или цветами."""
    child = Generation(
        id=uuid.uuid4(),
        user_id=parent.user_id,
        parent_id=parent.id,
        template_shift=template_shift,
        palette_shift=palette_shift,
        **{field: getattr(parent, field) for field in COPIED_FIELDS},
    )
    child.source_path = storage.generation_file(child.id, "source.jpg")
    copy_photo(parent, child)
    if parent.logo_path:
        child.logo_path = storage.generation_file(child.id, "logo.png")
        storage.copy_file(parent.logo_path, child.logo_path)
    return child


@router.post("/generations/{generation_id}/more")
def more_variants(generation_id: uuid.UUID, db: DbSession, user: CurrentUser):
    """«Ещё варианты»: следующие 4 темы."""
    parent = get_generation_or_404(db, generation_id, user)
    if limit_reached(db, user):
        return RedirectResponse("/pricing?limit=1", status_code=303)
    return enqueue(db, variation_of(parent, parent.template_shift + 1, parent.palette_shift))


@router.post("/generations/{generation_id}/recolor")
def other_colors(generation_id: uuid.UUID, db: DbSession, user: CurrentUser):
    """«Другие цвета»: те же темы, следующие палитры."""
    parent = get_generation_or_404(db, generation_id, user)
    if limit_reached(db, user):
        return RedirectResponse("/pricing?limit=1", status_code=303)
    return enqueue(db, variation_of(parent, parent.template_shift, parent.palette_shift + 1))


@router.post("/generations/{generation_id}/favorite/{variant}", response_class=HTMLResponse)
def toggle_favorite(
    request: Request, generation_id: uuid.UUID, variant: str, db: DbSession, user: CurrentUser
):
    """Звёздочка у варианта (HTMX). Любимые темы потом предлагаются первыми."""
    generation = get_generation_or_404(db, generation_id, user)
    banners = [b for b in generation.banners if b.variant == variant]
    if not banners:
        raise HTTPException(status_code=404, detail="Вариант не найден")
    new_value = not banners[0].favorite
    for banner in banners:
        banner.favorite = new_value
    db.commit()
    return templates.TemplateResponse(
        request,
        "partials/favorite_button.html",
        {"generation": generation, "variant": variant, "favorite": new_value},
    )


@router.post("/generations/{generation_id}/share", response_class=HTMLResponse)
def share(
    request: Request, generation_id: uuid.UUID, db: DbSession, user: CurrentUser, off: bool = False
):
    """Включить / выключить ссылку «поделиться» (HTMX)."""
    generation = get_generation_or_404(db, generation_id, user)
    if off:
        generation.share_token = None
    elif not generation.share_token:
        generation.share_token = secrets.token_urlsafe(16)  # 22 символа — не угадать
    db.commit()
    return templates.TemplateResponse(
        request, "partials/share_box.html", {"generation": generation}
    )


@router.get("/s/{token}", response_class=HTMLResponse)
def shared_page(request: Request, token: str, db: DbSession):
    """Публичная страница по ссылке «поделиться»: только просмотр и скачивание, без входа."""
    generation = db.scalar(select(Generation).where(Generation.share_token == token))
    if generation is None or not token:
        raise HTTPException(status_code=404, detail="Ссылка недействительна")
    return templates.TemplateResponse(request, "shared.html", {"generation": generation})


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
    return zip_response(get_generation_or_404(db, generation_id, user))


@router.get("/s/{token}/banners.zip")
def download_all_shared(token: str, db: DbSession):
    """Архив по ссылке «поделиться»."""
    generation = db.scalar(select(Generation).where(Generation.share_token == token))
    if generation is None:
        raise HTTPException(status_code=404, detail="Ссылка недействительна")
    return zip_response(generation)


def zip_response(generation: Generation) -> Response:
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

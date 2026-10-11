"""Загрузка фото и страница результата обработки."""

import uuid
from typing import Annotated

from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.config import settings
from app.db import DbSession
from app.models import Generation
from app.services import storage
from app.services.images import ImageValidationError, prepare_source_image
from app.tasks import process_generation
from app.templating import templates

router = APIRouter()


def get_generation_or_404(db: Session, generation_id: uuid.UUID) -> Generation:
    generation = db.get(Generation, generation_id)
    if generation is None:
        raise HTTPException(status_code=404, detail="Генерация не найдена")
    return generation


def render_create_page(request: Request, error: str | None = None, status_code: int = 200):
    return templates.TemplateResponse(
        request,
        "create.html",
        {"error": error, "max_upload_mb": settings.max_upload_mb},
        status_code=status_code,
    )


@router.get("/create", response_class=HTMLResponse)
def create_page(request: Request):
    return render_create_page(request)


@router.post("/generations")
def create_generation(
    request: Request,
    db: DbSession,
    photo: Annotated[UploadFile | None, File()] = None,
):
    """Принимает фото, сохраняет его и ставит обработку в очередь Celery."""
    if photo is None or not photo.filename:
        return render_create_page(request, "Выберите фото товара.", status_code=400)
    if photo.size is not None and photo.size > settings.max_upload_mb * 1024 * 1024:
        return render_create_page(
            request, f"Файл больше {settings.max_upload_mb} МБ.", status_code=400
        )

    try:
        image = prepare_source_image(photo.file)
    except ImageValidationError as exc:
        return render_create_page(request, str(exc), status_code=400)

    generation = Generation(id=uuid.uuid4())
    generation.source_path = storage.generation_file(generation.id, "source.jpg")
    storage.save_image(image, generation.source_path, format="JPEG", quality=92)
    db.add(generation)
    # Сначала сохраняем в базу, потом ставим задачу — иначе воркер может не найти запись
    db.commit()
    process_generation.delay(str(generation.id))

    # 303 — после POST браузер переходит на страницу результата обычным GET
    return RedirectResponse(f"/generations/{generation.id}", status_code=303)


@router.get("/generations/{generation_id}", response_class=HTMLResponse)
def generation_page(request: Request, generation_id: uuid.UUID, db: DbSession):
    generation = get_generation_or_404(db, generation_id)
    return templates.TemplateResponse(request, "generation.html", {"generation": generation})


@router.get("/generations/{generation_id}/status", response_class=HTMLResponse)
def generation_status(request: Request, generation_id: uuid.UUID, db: DbSession):
    """HTMX-фрагмент: прогресс, пока идёт обработка, затем результат."""
    generation = get_generation_or_404(db, generation_id)
    return templates.TemplateResponse(
        request, "partials/generation_status.html", {"generation": generation}
    )

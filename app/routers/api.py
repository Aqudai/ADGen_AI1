"""JSON-эндпоинты: приветствие, проверка здоровья, статус генерации."""

import uuid

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.config import settings
from app.db import DbSession
from app.routers.generations import get_generation_or_404
from app.schemas import GenerationOut
from app.services.health import run_checks

router = APIRouter()


@router.get("/api/hello")
def hello() -> dict[str, str]:
    return {"message": f"Привет! Это {settings.app_name}."}


@router.get("/health")
def health() -> JSONResponse:
    """200 — все компоненты работают, 503 — что-то недоступно (видно в checks)."""
    checks = run_checks()
    ok = all(checks.values())
    return JSONResponse(
        status_code=200 if ok else 503,
        content={"status": "ok" if ok else "degraded", "checks": checks},
    )


@router.get("/api/generations/{generation_id}", response_model=GenerationOut)
def generation_detail(generation_id: uuid.UUID, db: DbSession):
    return get_generation_or_404(db, generation_id)

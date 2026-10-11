"""Точка входа веб-приложения AdGen AI."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.routers import api, pages

settings.media_dir.mkdir(parents=True, exist_ok=True)

app = FastAPI(title=settings.app_name, debug=settings.debug)

# Статика (css/картинки интерфейса) и пользовательские файлы (фото, баннеры)
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")
app.mount("/media", StaticFiles(directory=settings.media_dir), name="media")

app.include_router(pages.router)
app.include_router(api.router)

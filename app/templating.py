"""Общий объект Jinja2-шаблонов для всех роутеров."""

from pathlib import Path

from fastapi.templating import Jinja2Templates

from app.config import settings

templates = Jinja2Templates(directory=Path(__file__).parent / "templates")
# Переменные, доступные в любом шаблоне
templates.env.globals["app_name"] = settings.app_name

"""Общий объект Jinja2-шаблонов для всех роутеров."""

from pathlib import Path

from fastapi.templating import Jinja2Templates

from app.config import settings
from app.services.design import FONT_LABELS
from app.services.presets import TWOGIS_TITLE_LIMIT
from app.services.scene import ai_scene_enabled

templates = Jinja2Templates(directory=Path(__file__).parent / "templates")
# Переменные, доступные в любом шаблоне
templates.env.globals["app_name"] = settings.app_name
templates.env.globals["twogis_title_limit"] = TWOGIS_TITLE_LIMIT
templates.env.globals["font_labels"] = FONT_LABELS
templates.env.globals["ai_scene_enabled"] = ai_scene_enabled

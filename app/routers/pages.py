"""HTML-страницы и HTMX-фрагменты."""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from app.services.health import run_checks
from app.templating import templates

router = APIRouter()

CHECK_LABELS = {
    "database": "База данных (PostgreSQL)",
    "redis": "Очередь задач (Redis)",
    "celery": "Фоновый воркер (Celery)",
}


@router.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse(request, "index.html")


@router.get("/partials/status", response_class=HTMLResponse)
def status_partial(request: Request):
    """Фрагмент со статусом компонентов — его подгружает HTMX на главной."""
    checks = [{"label": CHECK_LABELS[name], "ok": ok} for name, ok in run_checks().items()]
    return templates.TemplateResponse(request, "partials/status.html", {"checks": checks})

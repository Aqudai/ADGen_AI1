"""Точка входа веб-приложения AdGen AI."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.config import settings
from app.routers import account, api, auth, generations, pages

settings.media_dir.mkdir(parents=True, exist_ok=True)

app = FastAPI(title=settings.app_name, debug=settings.debug)

# Сессия в cookie, подписанной SECRET_KEY. httponly (по умолчанию) — JavaScript её не прочитает;
# same_site=lax — браузер не отправит cookie с POST-формы чужого сайта (защита от CSRF)
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.secret_key,
    same_site="lax",
    https_only=settings.cookie_secure,
    max_age=60 * 60 * 24 * 14,  # 2 недели
)

# Статика (css/картинки интерфейса) и пользовательские файлы (фото, баннеры)
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")
app.mount("/media", StaticFiles(directory=settings.media_dir), name="media")

app.include_router(pages.router)
app.include_router(auth.router)
app.include_router(account.router)
app.include_router(generations.router)
app.include_router(api.router)

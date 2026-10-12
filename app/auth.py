"""Кто сейчас вошёл: пользователь хранится в подписанной cookie сессии.

Cookie подписывает SessionMiddleware ключом SECRET_KEY: подменить user_id в ней нельзя —
подпись перестанет сходиться, и сессия будет считаться пустой.
"""

from typing import Annotated

from fastapi import Depends, HTTPException, Request

from app.db import DbSession
from app.models import User


def get_current_user(request: Request, db: DbSession) -> User | None:
    user_id = request.session.get("user_id")
    return db.get(User, user_id) if user_id else None


OptionalUser = Annotated[User | None, Depends(get_current_user)]


def require_user(request: Request, user: OptionalUser) -> User:
    """Зависимость для страниц только для вошедших: иначе — на страницу входа и обратно."""
    if user is None:
        raise HTTPException(
            status_code=303, headers={"Location": f"/login?next={request.url.path}"}
        )
    return user


CurrentUser = Annotated[User, Depends(require_user)]


def log_in(request: Request, user: User) -> None:
    request.session.clear()  # новая сессия при входе — старая (возможно, чужая) не переживёт вход
    request.session["user_id"] = user.id
    request.session["email"] = user.email  # для шапки сайта, без запроса к базе


def log_out(request: Request) -> None:
    request.session.clear()


def safe_next(url: str | None) -> str:
    """Куда вернуть после входа. Только внутренние адреса — иначе ссылкой
    вида /login?next=https://evil.example можно увести пользователя на чужой сайт."""
    if url and url.startswith("/") and not url.startswith("//"):
        return url
    return "/create"

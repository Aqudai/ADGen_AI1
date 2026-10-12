"""Регистрация, вход и выход."""

from typing import Annotated

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import ValidationError
from sqlalchemy import select

from app.auth import OptionalUser, log_in, log_out, safe_next
from app.db import DbSession
from app.models import User
from app.schemas import RegisterForm, first_error
from app.services.passwords import hash_password, verify_password
from app.templating import templates

router = APIRouter()


def render(request: Request, template: str, status_code: int = 200, **context):
    return templates.TemplateResponse(request, template, context, status_code=status_code)


@router.get("/register", response_class=HTMLResponse)
def register_page(request: Request, user: OptionalUser):
    if user:
        return RedirectResponse("/create", status_code=303)
    return render(request, "register.html", email="")


@router.post("/register")
def register(
    request: Request,
    db: DbSession,
    email: Annotated[str, Form()] = "",
    password: Annotated[str, Form()] = "",
    password_confirm: Annotated[str, Form()] = "",
):
    try:
        form = RegisterForm(email=email, password=password, password_confirm=password_confirm)
    except ValidationError as exc:
        return render(request, "register.html", 400, error=first_error(exc), email=email)

    if db.scalar(select(User).where(User.email == form.email)):
        error = "Пользователь с таким email уже есть. Войдите."
        return render(request, "register.html", 400, error=error, email=email)

    user = User(email=form.email, password_hash=hash_password(form.password))
    db.add(user)
    db.commit()
    log_in(request, user)
    # Сразу после регистрации — в профиль: заполнить название, логотип и цвета
    return RedirectResponse("/profile?welcome=1", status_code=303)


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request, user: OptionalUser, next: str | None = None):
    if user:
        return RedirectResponse(safe_next(next), status_code=303)
    return render(request, "login.html", email="", next=next or "")


@router.post("/login")
def login(
    request: Request,
    db: DbSession,
    email: Annotated[str, Form()] = "",
    password: Annotated[str, Form()] = "",
    next: Annotated[str, Form()] = "",
):
    user = db.scalar(select(User).where(User.email == email.strip().lower()))
    # Одно и то же сообщение для «нет такого email» и «неверный пароль» —
    # иначе по ответу можно узнать, кто зарегистрирован в сервисе
    if user is None or not verify_password(password, user.password_hash):
        error = "Неверный email или пароль."
        return render(request, "login.html", 400, error=error, email=email, next=next)
    log_in(request, user)
    return RedirectResponse(safe_next(next), status_code=303)


@router.post("/logout")
def logout(request: Request):
    # Только POST: выход по ссылке (GET) могла бы вызвать чужая страница через <img src>
    log_out(request)
    return RedirectResponse("/", status_code=303)

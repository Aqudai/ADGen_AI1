"""Тарифы и страница администратора."""

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select

from app.auth import CurrentUser, OptionalUser
from app.config import settings
from app.db import DbSession
from app.models import User
from app.services import stats
from app.services.limits import used_today
from app.templating import templates

router = APIRouter()


def require_admin(user: CurrentUser) -> User:
    """Только для email из ADMIN_EMAILS. Остальным — 404: не показываем, что страница есть."""
    if user.email.lower() not in settings.admins:
        raise HTTPException(status_code=404)
    return user


@router.get("/pricing", response_class=HTMLResponse)
def pricing(request: Request, db: DbSession, user: OptionalUser, limit: bool = False):
    return templates.TemplateResponse(
        request,
        "pricing.html",
        {
            "user": user,
            "limit_hit": limit,
            "free_daily_limit": settings.free_daily_limit,
            "used": used_today(db, user) if user else 0,
        },
    )


@router.post("/pricing/try-pro")
def try_pro(user: CurrentUser, db: DbSession):
    """Демо-режим: оплата в MVP не подключена, Pro включается кнопкой для показа на защите."""
    user.is_pro = not user.is_pro
    db.commit()
    return RedirectResponse("/pricing", status_code=303)


@router.get("/admin", response_class=HTMLResponse, dependencies=[Depends(require_admin)])
def admin_page(request: Request, db: DbSession):
    users = db.scalars(select(User).order_by(User.created_at.desc()).limit(50)).all()
    return templates.TemplateResponse(
        request, "admin.html", {"stats": stats.collect(db), "users": users}
    )


@router.post("/admin/users/{user_id}/pro", dependencies=[Depends(require_admin)])
def toggle_pro(user_id: int, db: DbSession):
    target = db.get(User, user_id)
    if target is None:
        raise HTTPException(status_code=404)
    target.is_pro = not target.is_pro
    db.commit()
    return RedirectResponse("/admin", status_code=303)

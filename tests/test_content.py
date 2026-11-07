"""Цены, календарь поводов и проверка полей формы."""

from datetime import date

import pytest
from pydantic import ValidationError

from app.schemas import BannerRequest, BrandForm, normalize_price
from app.services.occasions import black_friday, upcoming

NBSP = " "


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("3990", f"3{NBSP}990{NBSP}₸"), ("12 500", f"12{NBSP}500{NBSP}₸"), ("$5", "$5"), ("", None)],
)
def test_normalize_price(raw, expected):
    assert normalize_price(raw) == expected


def test_banner_request_extra_fields():
    request = BannerRequest(promo_text="Акция", formats=["post"], price="990", cta="  Звоните ")
    assert request.price == f"990{NBSP}₸"
    assert request.cta == "Звоните"
    assert request.deadline is None
    with pytest.raises(ValidationError, match="Призыв"):
        BannerRequest(promo_text="Акция", formats=["post"], cta="я" * 31)


def test_qr_url_gets_https():
    form = BrandForm(
        business_name="", primary_color="#000000", secondary_color="#FFFFFF", qr_url="wa.me/7777"
    )
    assert form.qr_url == "https://wa.me/7777"
    with pytest.raises(ValidationError, match="QR"):
        BrandForm(
            business_name="", primary_color="#000000", secondary_color="#FFFFFF", qr_url="не ссылка"
        )


def test_black_friday():
    assert black_friday(2026) == date(2026, 11, 27)


def test_upcoming_occasion():
    assert upcoming(date(2026, 3, 15)).name == "Наурыз"
    assert upcoming(date(2026, 12, 25)).name == "Новый год"  # через границу года
    assert upcoming(date(2026, 7, 10)) is None  # летом поводов в календаре нет

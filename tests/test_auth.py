"""Регистрация, вход, выход, доступ к страницам."""

import uuid

import pytest

from app.models import User
from app.services.passwords import hash_password, verify_password
from tests.conftest import make_image_bytes, register


def test_password_hash_is_salted_and_verifiable():
    first, second = hash_password("secret123"), hash_password("secret123")
    assert first != second  # разная соль — разные хеши
    assert "secret123" not in first
    assert verify_password("secret123", first)
    assert not verify_password("wrong-pass", first)
    assert not verify_password("secret123", "garbage")


def test_register_logs_in_and_stores_hash(client, session_factory):
    response = register(client, email="  New@Example.com ")
    assert response.status_code == 303
    assert response.headers["location"] == "/profile?welcome=1"
    with session_factory() as db:
        user = db.query(User).one()
    assert user.email == "new@example.com"  # email приводится к нижнему регистру
    assert user.password_hash.startswith("scrypt$")
    assert client.get("/create").status_code == 200  # уже вошли


@pytest.mark.parametrize(
    ("email", "password", "confirm", "message"),
    [
        ("not-an-email", "secret123", "secret123", "корректный email"),
        ("a@b.kz", "short", "short", "не короче 8"),
        ("a@b.kz", "secret123", "secret124", "не совпадают"),
    ],
)
def test_register_validation(client, email, password, confirm, message):
    response = client.post(
        "/register", data={"email": email, "password": password, "password_confirm": confirm}
    )
    assert response.status_code == 400
    assert message in response.text


def test_register_duplicate_email(client):
    register(client)
    client.post("/logout")
    response = register(client)
    assert response.status_code == 400
    assert "уже есть" in response.text


def test_login_logout(client):
    register(client)
    client.post("/logout")
    assert client.get("/create", follow_redirects=False).status_code == 303

    bad = client.post("/login", data={"email": "owner@example.com", "password": "nope-nope"})
    assert bad.status_code == 400
    assert "Неверный email или пароль" in bad.text

    ok = client.post(
        "/login",
        data={"email": "owner@example.com", "password": "secret123", "next": "/history"},
        follow_redirects=False,
    )
    assert ok.headers["location"] == "/history"


def test_login_does_not_redirect_to_other_sites(client):
    register(client)
    client.post("/logout")
    response = client.post(
        "/login",
        data={"email": "owner@example.com", "password": "secret123", "next": "//evil.example"},
        follow_redirects=False,
    )
    assert response.headers["location"] == "/create"


@pytest.mark.parametrize("url", ["/create", "/profile", "/history"])
def test_pages_require_login(client, url):
    response = client.get(url, follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == f"/login?next={url}"


def test_tampered_session_cookie_is_ignored(client):
    register(client)
    client.cookies.set("session", "forged-value")
    assert client.get("/create", follow_redirects=False).status_code == 303


def test_other_users_generation_is_hidden(client, monkeypatch):
    from app.routers import generations

    class FakeTask:
        def delay(self, *args):
            pass

    monkeypatch.setattr(generations, "process_generation", FakeTask())
    register(client, email="alice@example.com")
    response = client.post(
        "/generations",
        data={"promo_text": "Акция", "style": "cozy", "formats": ["post"]},
        files={"photo": ("p.jpg", make_image_bytes(), "image/jpeg")},
        follow_redirects=False,
    )
    url = response.headers["location"]
    assert client.get(url).status_code == 200

    client.post("/logout")
    register(client, email="bob@example.com")
    assert client.get(url).status_code == 404
    assert client.get(f"/api/generations/{url.rsplit('/', 1)[1]}").status_code == 404
    assert client.get(f"/generations/{uuid.uuid4()}").status_code == 404

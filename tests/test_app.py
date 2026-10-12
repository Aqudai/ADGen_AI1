"""Тесты Спринта 0: приложение запускается, страницы и API отвечают.

Проверки базы/Redis/Celery подменяются (monkeypatch), поэтому тесты
не требуют запущенных контейнеров.
"""

from app.config import Settings
from app.routers import api


def test_hello(client):
    response = client.get("/api/hello")
    assert response.status_code == 200
    assert "AdGen AI" in response.json()["message"]


def test_index_page(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Рекламные баннеры" in response.text
    assert 'href="/register"' in response.text  # гостю — кнопка регистрации


def test_health_ok(client, monkeypatch):
    monkeypatch.setattr(
        api, "run_checks", lambda: {"database": True, "redis": True, "celery": True}
    )
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_health_degraded(client, monkeypatch):
    monkeypatch.setattr(
        api, "run_checks", lambda: {"database": True, "redis": False, "celery": False}
    )
    response = client.get("/health")
    assert response.status_code == 503
    assert response.json()["checks"]["redis"] is False


def test_secret_key_placeholder_rejected_in_production():
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError, match="SECRET_KEY"):
        Settings(
            secret_key="change-me",
            debug=False,
            postgres_user="a",
            postgres_password="b",
            postgres_db="c",
        )


def test_database_url_escapes_password():
    settings = Settings(
        secret_key="x",
        postgres_user="adgen",
        postgres_password="p@ss:word",
        postgres_db="adgen",
    )
    url = settings.database_url
    assert url.drivername == "postgresql+psycopg"
    assert url.password == "p@ss:word"
    assert "p%40ss%3Aword" in url.render_as_string(hide_password=False)

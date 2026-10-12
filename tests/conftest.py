"""Общие фикстуры для тестов.

Тестовые значения переменных окружения выставляются ДО импорта приложения,
чтобы тесты запускались и без файла .env (например, в CI).
Вместо PostgreSQL тесты используют SQLite в памяти, вместо папки media/ — временную папку,
поэтому для тестов не нужны запущенные контейнеры.
"""

import io
import os

os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("POSTGRES_USER", "test")
os.environ.setdefault("POSTGRES_PASSWORD", "test")
os.environ.setdefault("POSTGRES_DB", "test")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from PIL import Image  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app import tasks  # noqa: E402
from app.config import settings  # noqa: E402
from app.db import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture
def session_factory(monkeypatch):
    """Чистая база SQLite в памяти на каждый тест."""
    # StaticPool — одно соединение на всех, иначе у каждого соединения своя пустая база
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    def override_get_db():
        with factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    monkeypatch.setattr(tasks, "SessionLocal", factory)  # задача Celery тоже пишет в SQLite
    yield factory
    app.dependency_overrides.clear()
    engine.dispose()


@pytest.fixture(autouse=True)
def media_dir(tmp_path, monkeypatch):
    """Файлы тестов пишутся во временную папку, а не в настоящую media/."""
    monkeypatch.setattr(settings, "media_dir", tmp_path)
    return tmp_path


@pytest.fixture
def client(session_factory) -> TestClient:
    return TestClient(app)


def make_image_bytes(size=(800, 600), color="red", fmt="JPEG", mode="RGB") -> bytes:
    """Картинка нужного размера и формата в виде байтов — как файл, пришедший из формы."""
    buffer = io.BytesIO()
    Image.new(mode, size, color).save(buffer, format=fmt)
    return buffer.getvalue()


def register(client: TestClient, email: str = "owner@example.com", password: str = "secret123"):
    """Регистрирует пользователя; после этого client «вошёл» (cookie сессии сохраняется)."""
    return client.post(
        "/register",
        data={"email": email, "password": password, "password_confirm": password},
        follow_redirects=False,
    )


@pytest.fixture
def user_client(client) -> TestClient:
    """Клиент от имени вошедшего пользователя."""
    assert register(client).status_code == 303
    return client

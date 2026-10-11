"""Подключение к PostgreSQL через SQLAlchemy."""

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings

# pool_pre_ping — проверять соединение перед использованием (если база перезапускалась)
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    connect_args={"connect_timeout": 3},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    """Базовый класс для всех моделей (таблиц)."""


def get_db() -> Iterator[Session]:
    """Зависимость FastAPI: открывает сессию на время запроса и закрывает после."""
    with SessionLocal() as session:
        yield session

"""Окружение Alembic: подключение и модели берём из приложения."""

from logging.config import fileConfig

from alembic import context

from app import models  # noqa: F401 — импорт регистрирует все модели в Base.metadata
from app.db import Base, engine

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# По этим метаданным autogenerate сравнивает модели с реальной базой
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Режим без подключения: печатает SQL (alembic upgrade head --sql)."""
    context.configure(
        url=engine.url.render_as_string(hide_password=False),
        target_metadata=target_metadata,
        literal_binds=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Обычный режим: применяет миграции к базе."""
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

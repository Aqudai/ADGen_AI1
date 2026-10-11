"""Настройки приложения.

Все значения читаются из переменных окружения (или файла .env) — так секреты
не попадают в код. Список переменных с пояснениями — в .env.example.
"""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "AdGen AI"
    debug: bool = False
    secret_key: str

    # PostgreSQL
    postgres_user: str
    postgres_password: str
    postgres_db: str
    postgres_host: str = "db"
    postgres_port: int = 5432

    # Redis: брокер очереди и хранилище результатов Celery
    redis_url: str = "redis://redis:6379/0"

    # Папка для загруженных фото и готовых баннеров
    media_dir: Path = Path("media")

    # Генерация фона нейросетью (используется со Спринта 2)
    image_provider: str = "huggingface"
    hf_api_token: str = ""

    @property
    def database_url(self) -> URL:
        """Адрес подключения к базе. URL.create сам экранирует спецсимволы в пароле."""
        return URL.create(
            "postgresql+psycopg",
            username=self.postgres_user,
            password=self.postgres_password,
            host=self.postgres_host,
            port=self.postgres_port,
            database=self.postgres_db,
        )


settings = Settings()

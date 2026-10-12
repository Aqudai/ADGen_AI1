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
    max_upload_mb: int = 10

    # Модель rembg для удаления фона. isnet-general-use точнее стандартной u2net
    # на фото товаров. Модель по умолчанию скачивается при сборке Docker-образа.
    rembg_model: str = "isnet-general-use"

    # Генерация сцены нейросетью.
    # IMAGE_PROVIDER: huggingface — нейросеть через Hugging Face; fallback — всегда запасной фон
    image_provider: str = "huggingface"
    # Имя HF_TOKEN выбрано не случайно: его же читает библиотека huggingface_hub
    hf_token: str = ""
    # Модель и провайдер (партнёр Hugging Face, который выполняет запрос). FLUX.1-schnell —
    # диффузионная модель от авторов Stable Diffusion: быстрая и дешёвая (~$0.0014 за картинку).
    # Другие варианты — в .env.example и docs/ARCHITECTURE.md.
    hf_provider: str = "nscale"
    hf_model: str = "black-forest-labs/FLUX.1-schnell"
    hf_timeout: int = 90  # секунд ждать картинку

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

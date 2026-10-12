# Один образ для веб-сервера и воркера Celery — различаются только командой запуска
FROM python:3.12-slim

# Не создавать .pyc и сразу выводить логи (без буферизации)
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Сначала зависимости — этот слой кешируется и не пересобирается при правке кода.
# Для разработки ставим и dev-зависимости (pytest, ruff); на сервере — INSTALL_DEV=false.
ARG INSTALL_DEV=true
COPY requirements.txt requirements-dev.txt ./
RUN if [ "$INSTALL_DEV" = "true" ]; then pip install --no-cache-dir -r requirements-dev.txt; \
    else pip install --no-cache-dir -r requirements.txt; fi

# Модель удаления фона (~180 МБ) скачиваем при сборке образа, а не при первой задаче,
# чтобы первая обработка не ждала загрузку. REMBG_HOME — куда rembg складывает модели.
ENV REMBG_HOME=/opt/rembg
RUN python -c "from rembg import new_session; new_session('isnet-general-use')"

# Приложение работает не от root: если в коде найдётся уязвимость,
# у злоумышленника не будет прав администратора внутри контейнера
RUN useradd --create-home --uid 1000 app && mkdir -p /app/media && chown -R app /app /opt/rembg
COPY --chown=app . .
USER app

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

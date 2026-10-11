# Один образ для веб-сервера и воркера Celery — различаются только командой запуска
FROM python:3.12-slim

# Не создавать .pyc и сразу выводить логи (без буферизации)
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Сначала зависимости — этот слой кешируется и не пересобирается при правке кода.
# Для разработки ставим и dev-зависимости (pytest, ruff); на деплое хватит requirements.txt.
COPY requirements.txt requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements-dev.txt

COPY . .

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

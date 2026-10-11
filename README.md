# AdGen AI

Веб-сервис, который делает рекламные изображения для малого бизнеса: кафе, магазинов, салонов.
Пользователь загружает фото товара, вводит текст акции, выбирает стиль и форматы — сервис
возвращает 3–4 готовых баннера (пост 1080×1080, сторис 1080×1920, баннер 2GIS).

Учебный семестровый проект по дисциплине «Управление проектами».
Команда: **Куантканов Думан**, **Кайролла Диас** (группа ТИИ-44).

**Текущий статус:** Спринт 0 — каркас проекта ✅

**Стек:** FastAPI · Pydantic v2 · SQLAlchemy 2 + Alembic · PostgreSQL · Celery + Redis ·
Jinja2 + HTMX + Tailwind CSS · Docker Compose · pytest · ruff

Архитектура, схемы компонентов и модель данных — в [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

---

## Что нужно установить

1. **Docker Desktop** — https://www.docker.com/products/docker-desktop/
   На Windows при установке оставьте галочку «Use WSL 2». После установки **запустите**
   Docker Desktop и дождитесь статуса «Engine running».
2. **Git** — https://git-scm.com/downloads

Python ставить на компьютер **не нужно**: всё работает внутри контейнеров.

> Команды `docker compose ...` одинаковые на Windows (PowerShell), macOS и Linux.
> Где команды отличаются, приведены оба варианта.

---

## Запуск с нуля

### 1. Скачать проект

```bash
git clone https://github.com/Aqudai/ADGen_AI1.git
cd ADGen_AI1
```

### 2. Создать файл `.env` с настройками

В репозитории лежит шаблон `.env.example`, а сам `.env` (с паролями и ключами) в git не попадает.

Windows (PowerShell):

```powershell
Copy-Item .env.example .env
```

macOS / Linux:

```bash
cp .env.example .env
```

Откройте `.env` в редакторе и замените `change-me` в `SECRET_KEY` и `POSTGRES_PASSWORD`
на свои значения. Случайную строку можно получить так (команда одинаковая для всех ОС):

```bash
docker run --rm python:3.12-slim python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### 3. Собрать и запустить

```bash
docker compose up --build
```

Первый запуск занимает несколько минут: скачиваются образы и ставятся зависимости.
Готово, когда в логах появится `Application startup complete` и `celery@... ready`.

При старте контейнер `web` сам применяет миграции базы (`alembic upgrade head`).

Чтобы запускать в фоне и не занимать терминал, добавьте `-d`: `docker compose up --build -d`.

### 4. Открыть в браузере

http://localhost:8000. Внизу главной страницы, в блоке «Состояние системы», все три пункта
должны быть зелёными: база данных, Redis и воркер Celery.

---

## Как проверить Спринт 0

Команды выполняются во **втором** терминале в папке проекта, пока работает `docker compose up`.

| Что проверяем | Как | Ожидаемый результат |
|---|---|---|
| Главная страница | http://localhost:8000 | Страница открывается, «Состояние системы» — три зелёных «работает» |
| FastAPI «hello» | http://localhost:8000/api/hello | `{"message":"Привет! Это AdGen AI."}` |
| Здоровье сервиса | http://localhost:8000/health | `{"status":"ok","checks":{"database":true,"redis":true,"celery":true}}` |
| Документация API | http://localhost:8000/docs | Swagger UI со списком эндпоинтов |
| Celery выполняет задачи | `docker compose exec web python -c "from app.tasks import ping; print(ping.delay().get(timeout=10))"` | `pong` |
| Миграция применена | `docker compose exec web alembic current` | `0001 (head)` |
| Таблицы в базе | `docker compose exec db psql -U adgen -d adgen -c "\dt"` | таблицы `users` и `alembic_version` |
| Тесты | `docker compose exec web pytest` | `6 passed` |
| Линтер | `docker compose exec web ruff check .` | `All checks passed!` |
| Адаптивность | В браузере F12 → значок телефона (Device Toolbar) | Вёрстка в одну колонку, без горизонтальной прокрутки |

Проверка, что сбой виден: `docker compose stop worker`, обновите блок «Состояние системы» →
воркер станет красным, а `/health` вернёт код 503. Вернуть: `docker compose start worker`.

---

## Полезные команды

| Задача | Команда |
|---|---|
| Логи всех сервисов (в реальном времени) | `docker compose logs -f` |
| Логи только воркера | `docker compose logs -f worker` |
| Остановить проект | `docker compose down` |
| Остановить и **удалить базу** (начать с чистого листа) | `docker compose down -v` |
| Пересобрать после изменения `requirements*.txt` | `docker compose up --build` |
| Перезапустить воркер после изменения задач | `docker compose restart worker` |
| Отформатировать код | `docker compose exec web ruff format .` |
| Консоль базы данных (psql) | `docker compose exec db psql -U adgen -d adgen` |

Код в контейнерах берётся прямо из папки проекта, поэтому веб-сервер перезапускается сам
при сохранении файла. Воркер Celery сам не перезапускается, после правки задач нужен
`docker compose restart worker`.

### Миграции базы данных (Alembic)

Изменили модели в `app/models.py`? Создайте и примените миграцию:

```bash
docker compose exec web alembic revision --autogenerate -m "add generations table"
docker compose exec web alembic upgrade head
```

Новый файл появится в `alembic/versions/`. Просмотрите его и закоммитьте вместе с моделью.
Напарник после `git pull` получит изменения базы просто перезапуском `web`.

| Задача | Команда |
|---|---|
| Текущая версия схемы | `docker compose exec web alembic current` |
| Откатить последнюю миграцию | `docker compose exec web alembic downgrade -1` |
| Показать SQL всех миграций (для отчёта) | `docker compose exec web alembic upgrade head --sql` |

### Подключение к базе из DBeaver / pgAdmin

Host `localhost`, порт `5433`, база, пользователь и пароль — из вашего `.env`.
Порт 5433 выбран, чтобы не конфликтовать с PostgreSQL, если он установлен на компьютере.

---

## Частые проблемы

**`Cannot connect to the Docker daemon` / `error during connect` / `pipe/dockerDesktopLinuxEngine`**
Docker Desktop не запущен. Запустите его и дождитесь «Engine running».

**`Bind for 0.0.0.0:8000 failed: port is already allocated`**
Порт 8000 занят другой программой. В `docker-compose.yml` замените `"8000:8000"` на
`"8001:8000"` и откройте http://localhost:8001.

**`password authentication failed for user "adgen"`**
Пароль в `.env` поменяли уже после первого запуска: база запомнила старый. Если данные не
нужны: `docker compose down -v`, затем `docker compose up`.

**`SecurityWarning: You're running the worker with superuser privileges` в логах воркера**
Ожидаемо при локальной разработке, на работу не влияет. Запуск под отдельным пользователем
настроим в Спринте 3 при подготовке к деплою.

**В браузере страница без стилей**
Tailwind CSS и HTMX подключаются через CDN, поэтому нужен интернет. Проверьте, что сайт
cdn.jsdelivr.net не заблокирован.

---

## Структура проекта

```
app/            код приложения: main.py, config.py, db.py, models.py, worker.py, tasks.py
  routers/      обработчики URL (страницы и API)
  services/     бизнес-логика (проверка здоровья; дальше — шаги пайплайна)
  templates/    HTML-шаблоны Jinja2
  static/       статика интерфейса
alembic/        миграции базы данных
tests/          тесты pytest
docs/           документация для отчётов
media/          загруженные и сгенерированные изображения (не в git)
```

Подробно — в [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

---

## План по спринтам (по 2 недели, MVP — начало декабря 2026)

| Спринт | Содержание | Статус |
|---|---|---|
| 0 | Структура проекта, docker-compose, FastAPI «hello», база + первая миграция, базовый шаблон с Tailwind, README, ARCHITECTURE.md | ✅ |
| 1 | Загрузка фото + удаление фона (rembg) в задаче Celery, показ результата | — |
| 2 | Генерация сцены нейросетью, композиция, текст и логотип, форматы, галерея и скачивание | — |
| 3 | Регистрация и вход, профиль бренда, история, лендинг, тесты, CI, подготовка к деплою | — |

После каждого спринта делаем git-коммит с понятным сообщением, например
`Спринт 1: загрузка фото и удаление фона`.

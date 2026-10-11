# AdGen AI

Веб-сервис, который делает рекламные изображения для малого бизнеса: кафе, магазинов, салонов.
Пользователь загружает фото товара, вводит текст акции, выбирает стиль и форматы — сервис
возвращает 3–4 готовых баннера (пост 1080×1080, сторис 1080×1920, баннер 2GIS).

Учебный семестровый проект по дисциплине «Управление проектами».
Команда: **Куантканов Думан**, **Кайролла Диас** (группа ТИИ-44).

**Текущий статус:** Спринт 1 — загрузка фото и удаление фона ✅

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

Первый запуск занимает 5–15 минут: скачиваются образы, ставятся зависимости и нейросеть для
удаления фона (~180 МБ). Итоговый образ весит около 1,5 ГБ. Следующие запуски — секунды.
Готово, когда в логах появится `Application startup complete` и `celery@... ready`.

При старте контейнер `web` сам применяет миграции базы (`alembic upgrade head`).

Чтобы запускать в фоне и не занимать терминал, добавьте `-d`: `docker compose up --build -d`.

### 4. Открыть в браузере

http://localhost:8000. Внизу главной страницы, в блоке «Состояние системы», все три пункта
должны быть зелёными: база данных, Redis и воркер Celery.

Нажмите **«Попробовать»**, загрузите фото товара — через несколько секунд появится товар
без фона и кнопка «Скачать PNG без фона».

### Обновление проекта (когда в репозитории появились изменения)

```bash
git pull
docker compose up --build
```

`--build` обязателен, если изменились зависимости (`requirements*.txt`) или `Dockerfile`.
Миграции базы применятся сами при старте.

---

## Как проверить, что всё работает

Команды выполняются во **втором** терминале в папке проекта, пока работает `docker compose up`.

### Спринт 1: загрузка фото и удаление фона

| Что проверяем | Как | Ожидаемый результат |
|---|---|---|
| Загрузка фото | http://localhost:8000/create → перетащить фото в рамку (или нажать на неё и выбрать файл) | В рамке появляется превью фото и имя файла |
| Удаление фона | Нажать «Удалить фон» | Страница результата: «В очереди…» → «Удаляем фон…» → «Было / Стало» через 2–20 секунд |
| Скачивание | Кнопка «Скачать PNG без фона» | Скачивается PNG, фон прозрачный |
| Защита от неверных файлов | Загрузить текстовый файл, переименованный в `.jpg` | Сообщение «Не удалось открыть файл как изображение…» |
| Пустая форма | Нажать «Удалить фон», не выбрав фото | Сообщение «Сначала выберите фото товара.» |
| Статус в JSON | Скопировать id из адреса страницы результата → http://localhost:8000/api/generations/<id> | `"status":"done"` и ссылка `cutout_url` |
| Работа воркера | `docker compose logs worker` | Строки `Task app.tasks.process_generation[...] succeeded` |
| Таблица генераций | `docker compose exec web alembic current` | `0002 (head)` |
| Тесты | `docker compose exec web pytest` | `26 passed` |
| Вёрстка на телефоне | F12 → значок телефона (Device Toolbar) → страницы `/create` и результата | Всё в одну колонку, без горизонтальной прокрутки |

### Спринт 0: каркас

| Что проверяем | Как | Ожидаемый результат |
|---|---|---|
| Главная страница | http://localhost:8000 | Страница открывается, «Состояние системы» — три зелёных «работает» |
| FastAPI «hello» | http://localhost:8000/api/hello | `{"message":"Привет! Это AdGen AI."}` |
| Здоровье сервиса | http://localhost:8000/health | `{"status":"ok","checks":{"database":true,"redis":true,"celery":true}}` |
| Документация API | http://localhost:8000/docs | Swagger UI со списком эндпоинтов |
| Celery выполняет задачи | `docker compose exec web python -c "from app.tasks import ping; print(ping.delay().get(timeout=10))"` | `pong` |
| Таблицы в базе | `docker compose exec db psql -U adgen -d adgen -c "\dt"` | таблицы `users`, `generations` и `alembic_version` |
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
| Быстрые тесты (без настоящей нейросети) | `docker compose exec web pytest -m "not slow"` |
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

**Воркер падает, в логах `exited with code 137` или `SIGKILL`**
Не хватает памяти: каждый процесс воркера держит нейросеть (~0,9 ГБ), всего ~2 ГБ.
Увеличьте память в Docker Desktop → Settings → Resources или в `docker-compose.yml`
замените `--concurrency=2` на `--concurrency=1`.

**Обработка висит на «В очереди…»**
Воркер не запущен или упал: `docker compose ps` и `docker compose logs worker`.

**Фото с iPhone не загружается**
Формат HEIC не поддерживается. При загрузке через браузер на iPhone фото обычно
автоматически конвертируется в JPG; если нет — сохраните фото как JPG.

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
| 1 | Загрузка фото + удаление фона (rembg) в задаче Celery, показ результата | ✅ |
| 2 | Генерация сцены нейросетью, композиция, текст и логотип, форматы, галерея и скачивание | — |
| 3 | Регистрация и вход, профиль бренда, история, лендинг, тесты, CI, подготовка к деплою | — |

После каждого спринта делаем git-коммит с понятным сообщением, например
`Спринт 1: загрузка фото и удаление фона`.

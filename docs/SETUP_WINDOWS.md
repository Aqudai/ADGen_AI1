# AdGen AI — запуск на Windows с нуля (Docker, Git, PowerShell)

> Этот файл можно целиком отправить в другой чат (ИИ-ассистенту или напарнику):
> в нём есть всё, чтобы помочь запустить проект и разобраться с ошибками.

## Коротко о проекте (контекст для помощника)

- **Что это:** учебный проект группы ТИИ-44 (дисциплина «Управление проектами») — веб-сервис
  рекламных баннеров для малого бизнеса. Пользователь загружает фото товара, пишет текст
  акции и пожелание к дизайну — сервис делает 4 варианта баннеров (пост, сторис, карусель,
  видео-сторис, фото для 2GIS).
- **Репозиторий:** https://github.com/Aqudai/ADGen_AI1 (ветка по умолчанию
  `claude/adgen-ai-banner-service-ivwbkh` — единственная, `git clone` скачает её сам).
- **Стек:** Python 3.12, FastAPI, Jinja2 + HTMX + Tailwind CSS (через CDN), PostgreSQL 16,
  Redis 7, Celery, SQLAlchemy 2 + Alembic, Pillow, rembg (нейросеть удаления фона, работает
  локально), PyAV (видео). Всё запускается в Docker Compose: сервисы `web`, `worker`, `db`, `redis`.
- **На компьютер ставить Python, PostgreSQL и т.п. НЕ нужно** — всё внутри Docker.
- **Платные сервисы не нужны.** Ключ Hugging Face (`HF_TOKEN`) — необязательный, без него всё работает.
- Документация в репозитории: `README.md` (запуск и чек-листы проверки), `docs/ARCHITECTURE.md`
  (архитектура), `docs/PROJECT_MANAGEMENT.md` (бэклог, спринты, риски — для отчёта),
  `docs/DEPLOY.md` (сервер).

---

## Шаг 1. Установить программы (один раз)

1. **Docker Desktop** — https://www.docker.com/products/docker-desktop/
   - При установке оставьте галочку **Use WSL 2**.
   - После установки перезагрузите компьютер, запустите Docker Desktop и дождитесь внизу
     слева зелёной надписи **Engine running**.
2. **Git** — https://git-scm.com/download/win (при установке везде «Next»).
3. (По желанию) **PyCharm** — https://www.jetbrains.com/pycharm/download/ — чтобы смотреть код.

Проверка — откройте **PowerShell** (Пуск → набрать «PowerShell») и выполните:

```powershell
docker --version
docker compose version
git --version
```

Каждая команда должна напечатать номер версии. Если `docker` «не найден» — Docker Desktop
не установлен или не запущен; если `git` не найден — закройте и заново откройте PowerShell
после установки Git.

## Шаг 2. Скачать проект

```powershell
cd $HOME\Documents
git clone https://github.com/Aqudai/ADGen_AI1.git
cd ADGen_AI1
```

Проект окажется в папке `Документы\ADGen_AI1`.

## Шаг 3. Создать файл настроек `.env` (один раз)

```powershell
Copy-Item .env.example .env
notepad .env
```

В открывшемся Блокноте поменяйте и сохраните (Ctrl+S):

| Строка | Что вписать |
|---|---|
| `SECRET_KEY=change-me` | любая длинная случайная строка (30–40 букв и цифр) |
| `POSTGRES_PASSWORD=change-me` | любой пароль для базы |
| `ADMIN_EMAILS=` | ваш email — тогда после регистрации с ним будет доступна страница «Статистика» |
| `HF_TOKEN=` | можно оставить пустым |

Файл `.env` в GitHub не попадает — он у каждого свой. Ключи и пароли никому не отправляйте.

## Шаг 4. Запустить

```powershell
docker compose up --build
```

- **Первый запуск — 5–15 минут:** скачиваются образы (~2 ГБ), библиотеки и нейросеть удаления фона.
- Готово, когда бег текста остановится и появятся строки `Application startup complete`
  и `celery@... ready`.
- Окно PowerShell **не закрывать** — пока оно открыто, сайт работает. Остановить — `Ctrl + C`.

Откройте в браузере: **http://localhost:8000**

## Шаг 5. Проверить, что всё работает

1. http://localhost:8000/health → должно быть `"status":"ok"`.
2. **Регистрация** → email и пароль (от 8 символов).
3. **Профиль бренда:** название, логотип, цвета, контакты, ссылка для QR-кода (например,
   `wa.me/77771234567`) → «Сохранить».
4. **Создать:** загрузить фото товара, написать текст акции (например, «Скидка 20% на кофе
   до пятницы»), нажать подсказку пожелания (например, «Премиум, чёрный с золотом»),
   по желанию — цена и срок → **«Сгенерировать баннеры»**.
5. Через 10–60 секунд — 4 варианта. Попробовать «Ещё варианты», «Другие цвета», звёздочку,
   «Поделиться ссылкой», «Скачать все (ZIP)».

Полный чек-лист проверки по спринтам — в `README.md`.

---

## Ежедневная работа

| Что нужно | Команда (PowerShell, в папке `ADGen_AI1`) |
|---|---|
| Перейти в папку проекта | `cd $HOME\Documents\ADGen_AI1` |
| Запустить | `docker compose up` |
| Запустить в фоне (окно можно закрыть) | `docker compose up -d` |
| Остановить | `Ctrl + C` или `docker compose down` |
| Посмотреть логи | `docker compose logs -f` |
| Запустить тесты | `docker compose exec web pytest` |
| Полностью сбросить (удалит пользователей и баннеры!) | `docker compose down -v` |

Перед работой Docker Desktop должен быть запущен.

## Git: обновления и работа вдвоём

**Один раз — представиться Git:**

```powershell
git config --global user.name "Ваше Имя"
git config --global user.email "ваш@email.com"
```

**Доступ напарнику:** владелец репозитория на GitHub → репозиторий → **Settings** →
**Collaborators** → **Add people** → GitHub-ник напарника. Напарник принимает приглашение из почты.

**Получить свежие изменения** (каждый раз перед работой):

```powershell
git pull
docker compose up --build
```

`--build` нужен, если изменились зависимости (`requirements*.txt`) или `Dockerfile`;
миграции базы применяются сами при старте.

**Отправить свои изменения:**

```powershell
git status
git add .
git commit -m "Коротко: что изменил"
git push
```

Правила: всегда `git pull` перед началом работы; не править один и тот же файл
одновременно; `.env` никогда не коммитить (Git его и так игнорирует).

---

## Частые проблемы

| Сообщение / симптом | Что делать |
|---|---|
| `error during connect` / `Cannot connect to the Docker daemon` / `dockerDesktopLinuxEngine` | Не запущен Docker Desktop — запустить, дождаться «Engine running» |
| Docker Desktop пишет про **WSL** | В PowerShell **от имени администратора**: `wsl --update`, затем перезагрузка |
| Docker Desktop пишет про **виртуализацию** | Включить Virtualization (VT-x / SVM) в BIOS ноутбука |
| `port is already allocated` (порт 8000 или 5433) | Порт занят другой программой — закрыть её или перезагрузить компьютер |
| `password authentication failed for user "adgen"` | Пароль в `.env` поменяли после первого запуска: `docker compose down -v`, затем `docker compose up` |
| Воркер падает, `exited with code 137` | Мало памяти: Docker Desktop → Settings → Resources → дать 4 ГБ и больше |
| «В очереди…» висит долго | `docker compose ps` и `docker compose logs worker` — воркер не запущен или упал |
| Страница без стилей | Нет интернета: стили Tailwind и HTMX загружаются с CDN |
| «На бесплатном тарифе … лимит исчерпан» | В `.env` увеличить `FREE_DAILY_LIMIT`, затем `docker compose up -d`; или «Тарифы» → «Попробовать Pro» |
| Не видно пункта «Статистика» | В `.env` прописать `ADMIN_EMAILS=ваш@email`, `docker compose up -d`, выйти и войти заново |
| `git` не найден | Установить Git и заново открыть PowerShell |

Если ошибка другая — скопируйте её текст из PowerShell (или сделайте скриншот) и отправьте
помощнику вместе с этим файлом.

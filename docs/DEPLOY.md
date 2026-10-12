# Деплой AdGen AI на сервер

Инструкция для VPS с Ubuntu 24.04 (подойдёт любой хостинг с Docker; нужно от 4 ГБ памяти —
нейросеть удаления фона занимает ~2 ГБ). Проверено: `docker-compose.prod.yml` запускается,
регистрация и генерация баннеров работают, контейнеры работают не от root.

## Чем серверный запуск отличается от разработки

| | Разработка (`docker-compose.yml`) | Сервер (`docker-compose.prod.yml`) |
|---|---|---|
| Код | смонтирован из папки, автоперезагрузка | внутри образа |
| Зависимости | с pytest и ruff | только нужные для работы |
| Пользователь в контейнере | root (чтобы писать в папку проекта) | `app` (без прав администратора) |
| Веб-сервер | 1 процесс, `--reload` | 2 процесса, `--proxy-headers` |
| После сбоя / перезагрузки | не поднимается сам | `restart: unless-stopped` |
| База | открыта на порту 5433 | наружу не открыта |
| Файлы `media/` | папка проекта | том Docker `media`, общий для web и worker |

## 1. Подготовить сервер

```bash
# Docker (официальный скрипт)
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER   # перелогиньтесь после этой команды

git clone https://github.com/Aqudai/ADGen_AI1.git adgen
cd adgen
cp .env.example .env
```

## 2. Заполнить `.env`

Обязательно поменять:

```ini
DEBUG=false
SECRET_KEY=<длинная случайная строка>   # python3 -c "import secrets; print(secrets.token_urlsafe(32))"
POSTGRES_PASSWORD=<надёжный пароль>
COOKIE_SECURE=true                      # если сайт открывается по HTTPS (шаг 4)
HF_TOKEN=<ключ Hugging Face>            # необязательно, см. README
```

С `DEBUG=false` приложение не запустится, если `SECRET_KEY` остался `change-me` — это защита
от случайного запуска с ключом из примера.

## 3. Запустить

```bash
docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml ps        # все сервисы Up
curl http://127.0.0.1:8000/health                   # {"status":"ok",...}
```

Порт 8000 открыт только для самого сервера — снаружи сайт доступен через прокси (шаг 4).

## 4. Домен и HTTPS (Caddy)

Caddy сам получает и продлевает бесплатный сертификат Let's Encrypt. Направьте домен
(A-запись) на IP сервера, затем:

```bash
sudo apt install -y caddy
echo 'adgen.example.kz {
    reverse_proxy 127.0.0.1:8000
}' | sudo tee /etc/caddy/Caddyfile
sudo systemctl reload caddy
```

## 5. Обновление

```bash
git pull
docker compose -f docker-compose.prod.yml up -d --build   # миграции применятся сами
```

## 6. Резервная копия базы

```bash
docker compose -f docker-compose.prod.yml exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' > backup.sql
```

Баннеры лежат в томе Docker `media`; для копии: `docker run --rm -v adgen_media:/m -v "$PWD":/b alpine tar czf /b/media.tgz -C /m .`
(имя тома — `<папка проекта>_media`, посмотреть: `docker volume ls`).

## Что стоит сделать дальше (за рамками MVP)

- Хранить файлы в S3-совместимом хранилище вместо тома Docker (меняется только `app/services/storage.py`).
- Раздавать `media/` через Caddy/nginx, а не через FastAPI.
- Собирать Tailwind CSS при сборке образа вместо CDN.
- Подтверждение email и восстановление пароля.

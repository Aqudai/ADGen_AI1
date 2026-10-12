# AdGen AI — правила проекта для Claude

Учебный проект (группа ТИИ-44, «Управление проектами»): сервис рекламных баннеров для малого бизнеса.
Команда — новички: код должен быть простым и объяснимым на защите. Общение и комментарии — на русском.

## Где что
- README.md — запуск с нуля и чек-листы проверки по спринтам; docs/ARCHITECTURE.md — архитектура,
  решения и их причины (для отчётов); docs/DEPLOY.md — сервер.
- Код: app/ (FastAPI + Jinja2/HTMX/Tailwind CDN), шаги пайплайна — app/services/, задача Celery — app/tasks.py.
- Рабочая ветка: `claude/adgen-ai-banner-service-ivwbkh`.

## Правила
- Комментарии и docstring — по-русски, объясняют «зачем». Без «энтерпрайзных» абстракций.
- Секреты только в .env (в git — .env.example). Ключи из чата никуда не записывать.
- Изменение моделей → миграция Alembic (`alembic revision --autogenerate`), затем привести её к
  аккуратному виду с русским docstring; проверить `alembic check` и downgrade/upgrade.
- Внешние сервисы (Hugging Face) не должны ронять генерацию: ошибка → запасной фон + причина.
- Сообщения пользователю — по-русски и понятные.

## Проверка перед коммитом (всё внутри Docker)
```
docker compose up -d --build
docker compose exec web ruff check . && docker compose exec web ruff format --check .
docker compose exec web pytest            # -m "not slow" — без настоящей нейросети
```
UI проверять в браузере (десктоп и ширина телефона 390 px). После спринта — коммит
«Спринт N: ...», обновить README (чек-лист), docs/ARCHITECTURE.md (раздел «Что сделано»).

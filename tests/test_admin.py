"""Тарифы (дневной лимит, Pro) и страница статистики администратора."""

from app.config import settings
from app.models import User
from tests.conftest import make_image_bytes, register


class FakeTask:
    def delay(self, *args):
        pass


def submit(client):
    return client.post(
        "/generations",
        data={"promo_text": "Акция", "formats": ["post"]},
        files={"photo": ("p.jpg", make_image_bytes(), "image/jpeg")},
        follow_redirects=False,
    )


def test_daily_limit_and_pro(user_client, monkeypatch, session_factory):
    from app.routers import generations

    monkeypatch.setattr(generations, "process_generation", FakeTask())
    monkeypatch.setattr(settings, "free_daily_limit", 2)

    assert "сегодня 0 из 2" in user_client.get("/create").text
    assert submit(user_client).status_code == 303
    assert submit(user_client).status_code == 303
    blocked = submit(user_client)
    assert blocked.status_code == 400 and "лимит исчерпан" in blocked.text

    # Демо-подключение Pro снимает лимит
    user_client.post("/pricing/try-pro")
    with session_factory() as db:
        assert db.query(User).one().is_pro
    assert submit(user_client).status_code == 303


def test_pricing_page_for_guest(client):
    page = client.get("/pricing").text
    assert "Бесплатный" in page and "2 990 ₸" in page and 'href="/register"' in page


def test_admin_only_for_admin_emails(client, monkeypatch):
    register(client, email="user@example.com")
    assert client.get("/admin").status_code == 404

    monkeypatch.setattr(settings, "admin_emails", "boss@example.com")
    client.post("/logout")
    register(client, email="boss@example.com")
    page = client.get("/admin")
    assert page.status_code == 200
    assert "Генерации за 14 дней" in page.text and "user@example.com" in page.text
    assert 'href="/admin"' in page.text  # ссылка в шапке видна администратору


def test_admin_toggles_pro(client, monkeypatch, session_factory):
    monkeypatch.setattr(settings, "admin_emails", "boss@example.com")
    register(client, email="boss@example.com")
    with session_factory() as db:
        user_id = db.query(User).one().id
    client.post(f"/admin/users/{user_id}/pro")
    with session_factory() as db:
        assert db.get(User, user_id).is_pro


def test_stats_counts(user_client, monkeypatch, session_factory):
    from app.routers import generations
    from app.services import stats

    monkeypatch.setattr(generations, "process_generation", FakeTask())
    submit(user_client)
    with session_factory() as db:
        result = stats.collect(db)
    assert result["users"] == 1 and result["generations"] == 1 and result["today"] == 1
    assert len(result["timeline"]) == 14

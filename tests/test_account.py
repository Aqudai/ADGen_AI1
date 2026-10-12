"""Профиль бренда и история генераций."""

from app.models import BrandProfile
from tests.conftest import make_image_bytes


def test_profile_page_has_defaults(user_client):
    response = user_client.get("/profile?welcome=1")
    assert response.status_code == 200
    assert "Добро пожаловать" in response.text
    assert 'value="#4F46E5"' in response.text


def test_save_profile(user_client, session_factory, media_dir):
    logo = make_image_bytes((200, 100), fmt="PNG")
    response = user_client.post(
        "/profile",
        data={
            "business_name": " Кофейня «Зерно» ",
            "primary_color": "#aa00ff",
            "secondary_color": "#00AA00",
        },
        files={"logo": ("logo.png", logo, "image/png")},
        follow_redirects=False,
    )
    assert response.headers["location"] == "/profile?saved=1"
    with session_factory() as db:
        brand = db.query(BrandProfile).one()
    assert brand.business_name == "Кофейня «Зерно»"
    assert brand.primary_color == "#AA00FF"
    assert (media_dir / brand.logo_path).exists()

    # Удаление логотипа
    user_client.post(
        "/profile",
        data={
            "business_name": "Зерно",
            "primary_color": "#AA00FF",
            "secondary_color": "#00AA00",
            "remove_logo": "true",
        },
    )
    with session_factory() as db:
        assert db.query(BrandProfile).one().logo_path is None


def test_profile_validation_keeps_entered_values(user_client):
    response = user_client.post(
        "/profile",
        data={"business_name": "Моя кофейня", "primary_color": "red", "secondary_color": "#000000"},
    )
    assert response.status_code == 400
    assert "#RRGGBB" in response.text
    assert "Моя кофейня" in response.text


def test_profile_rejects_bad_logo(user_client):
    response = user_client.post(
        "/profile",
        data={"business_name": "", "primary_color": "#000000", "secondary_color": "#FFFFFF"},
        files={"logo": ("logo.png", b"not an image", "image/png")},
    )
    assert response.status_code == 400
    assert "Не удалось открыть логотип" in response.text


def test_history_empty_and_with_generation(user_client, monkeypatch):
    assert "Здесь пока пусто" in user_client.get("/history").text

    from app.routers import generations

    class FakeTask:
        def delay(self, *args):
            pass

    monkeypatch.setattr(generations, "process_generation", FakeTask())
    user_client.post(
        "/generations",
        data={"promo_text": "Скидка на латте", "style": "minimal", "formats": ["post"]},
        files={"photo": ("p.jpg", make_image_bytes(), "image/jpeg")},
    )
    history = user_client.get("/history").text
    assert "Скидка на латте" in history
    assert "В очереди" in history

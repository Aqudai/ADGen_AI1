"""Форма создания баннеров, задача Celery и страница результата."""

import io
import uuid
import zipfile

import pytest
from PIL import Image

from app import tasks
from app.config import settings
from app.models import Banner, Generation, GenerationStatus, SceneSource
from app.routers import generations
from tests.conftest import make_image_bytes

PROMO = "Скидка 20% на капучино до пятницы"


class FakeTask:
    """Заменяет задачу Celery: запоминает вызовы вместо отправки в Redis."""

    def __init__(self):
        self.calls = []

    def delay(self, *args):
        self.calls.append(args)


@pytest.fixture(autouse=True)
def fake_queue(monkeypatch) -> FakeTask:
    fake = FakeTask()
    monkeypatch.setattr(generations, "process_generation", fake)
    return fake


@pytest.fixture(autouse=True)
def no_ai(monkeypatch):
    """В тестах пайплайна сцену рисуем без нейросети (вызов HF проверяется в test_scene.py)."""
    monkeypatch.setattr(settings, "image_provider", "fallback")


def fake_remove_background(image: Image.Image) -> Image.Image:
    """Вместо нейросети: делает картинку полупрозрачной. Быстро и без модели."""
    cutout = image.convert("RGBA")
    cutout.putalpha(128)
    return cutout


def submit(client, photo=None, logo=None, **fields):
    data = {"promo_text": PROMO, "style": "cozy", "formats": ["post", "2gis"]} | fields
    files = {}
    if photo is not False:
        files["photo"] = ("photo.jpg", photo or make_image_bytes(), "image/jpeg")
    if logo is not None:
        files["logo"] = ("logo.png", logo, "image/png")
    return client.post("/generations", data=data, files=files, follow_redirects=False)


def created_generation(response, session_factory) -> Generation:
    generation_id = uuid.UUID(response.headers["location"].rsplit("/", 1)[1])
    with session_factory() as db:
        return db.get(Generation, generation_id)


def run_pipeline(client, monkeypatch, session_factory, **fields) -> Generation:
    """Создаёт генерацию через форму и выполняет задачу напрямую, без очереди."""
    generation = created_generation(submit(client, **fields), session_factory)
    monkeypatch.setattr(tasks, "remove_background", fake_remove_background)
    tasks.process_generation(str(generation.id))
    with session_factory() as db:
        generation = db.get(Generation, generation.id)
        assert generation.banners is not None  # загружаем баннеры, пока сессия открыта
        return generation


def test_create_page(client):
    response = client.get("/create")
    assert response.status_code == 200
    assert 'enctype="multipart/form-data"' in response.text
    assert 'name="promo_text"' in response.text
    assert response.text.count('name="style"') == 3
    assert response.text.count('name="formats"') == 3


def test_submit_saves_generation_and_queues_task(client, session_factory, media_dir, fake_queue):
    response = submit(client)

    assert response.status_code == 303
    generation = created_generation(response, session_factory)
    assert fake_queue.calls == [(str(generation.id),)]
    assert generation.status == GenerationStatus.PENDING
    assert generation.promo_text == PROMO
    assert generation.style == "cozy"
    assert generation.formats == ["post", "2gis"]
    assert (media_dir / generation.source_path).exists()
    assert generation.logo_path is None


@pytest.mark.parametrize(
    ("fields", "message"),
    [
        ({"promo_text": "   "}, "Введите текст акции"),
        ({"promo_text": "А" * 121}, "длиннее 120 символов"),
        ({"style": "neon"}, "Выберите стиль фона"),
        ({"formats": []}, "хотя бы один формат"),
        ({"formats": ["post", "billboard"]}, "Неизвестный формат"),
        ({"photo": False}, "Выберите фото"),
        ({"photo": b"not an image"}, "Не удалось открыть файл"),
        ({"logo": b"not an image"}, "Не удалось открыть логотип"),
    ],
)
def test_form_errors(client, fake_queue, fields, message):
    response = submit(client, **fields)
    assert response.status_code == 400
    assert message in response.text
    assert fake_queue.calls == []  # ничего не поставили в очередь


def test_form_keeps_entered_text_after_error(client):
    response = submit(client, style="neon", promo_text="Мой текст акции")
    assert "Мой текст акции" in response.text


def test_photo_too_large(client, monkeypatch):
    monkeypatch.setattr(settings, "max_upload_mb", 0)
    response = submit(client)
    assert response.status_code == 400
    assert "Фото больше" in response.text


def test_logo_keeps_transparency(client, session_factory, media_dir):
    logo = make_image_bytes((300, 100), color=(0, 0, 255, 0), fmt="PNG", mode="RGBA")
    generation = created_generation(submit(client, logo=logo), session_factory)
    saved = Image.open(media_dir / generation.logo_path)
    assert saved.mode == "RGBA"
    assert saved.getpixel((5, 5))[3] == 0


def test_pipeline_creates_banners(client, monkeypatch, session_factory, media_dir):
    generation = run_pipeline(
        client, monkeypatch, session_factory, formats=["post", "story", "2gis"]
    )

    assert generation.status == GenerationStatus.DONE
    assert generation.step is None
    assert generation.scene_source == SceneSource.FALLBACK
    # пост и сторис — по 2 варианта, 2GIS — 1 (без текста)
    assert [(b.format, b.variant) for b in generation.banners] == [
        ("post", "overlay"),
        ("post", "panel"),
        ("story", "overlay"),
        ("story", "panel"),
        ("2gis", "clean"),
    ]
    for banner in generation.banners:
        image = Image.open(media_dir / banner.image_path)
        assert (
            image.size
            == {"post": (1080, 1080), "story": (1080, 1920), "2gis": (1200, 624)}[banner.format]
        )
    assert (media_dir / generation.cutout_path).exists()
    assert (media_dir / generation.scene_path).exists()


def test_pipeline_with_logo(client, monkeypatch, session_factory):
    logo = make_image_bytes((300, 100), color="navy", fmt="PNG")
    generation = run_pipeline(client, monkeypatch, session_factory, logo=logo, formats=["post"])
    assert generation.status == GenerationStatus.DONE
    assert len(generation.banners) == 2


def test_pipeline_failure_is_saved(client, monkeypatch, session_factory):
    generation = created_generation(submit(client), session_factory)

    def broken_remove_background(image):
        raise RuntimeError("модель сломалась")

    monkeypatch.setattr(tasks, "remove_background", broken_remove_background)
    tasks.process_generation(str(generation.id))

    with session_factory() as db:
        generation = db.get(Generation, generation.id)
        assert generation.status == GenerationStatus.FAILED
        assert "Не удалось создать баннеры" in generation.error_message
        assert generation.banners == []


def test_status_partial_shows_current_step(client, session_factory):
    generation = created_generation(submit(client), session_factory)
    with session_factory() as db:
        db.get(Generation, generation.id).step = "scene"
        db.commit()

    response = client.get(f"/generations/{generation.id}/status")

    assert 'hx-trigger="every 1s"' in response.text  # опрос продолжается
    assert "Рисуем сцену" in response.text


def test_status_partial_shows_gallery_when_done(client, monkeypatch, session_factory):
    generation = run_pipeline(client, monkeypatch, session_factory)

    response = client.get(f"/generations/{generation.id}/status")

    assert "hx-trigger" not in response.text  # опрос прекращается
    assert "Скачать все баннеры" in response.text
    assert 'download="adgen-post-overlay.jpg"' in response.text
    assert 'download="adgen-2gis-clean.jpg"' in response.text
    assert "Фото для блока «Скидки»" in response.text


def test_scene_note_is_shown(client, monkeypatch, session_factory):
    monkeypatch.setattr(settings, "image_provider", "huggingface")
    monkeypatch.setattr(settings, "hf_token", "")
    generation = run_pipeline(client, monkeypatch, session_factory)

    response = client.get(f"/generations/{generation.id}")

    assert "Фон нарисован без нейросети" in response.text
    assert "HF_TOKEN" in response.text


def test_zip_contains_all_banners(client, monkeypatch, session_factory):
    generation = run_pipeline(client, monkeypatch, session_factory)

    response = client.get(f"/generations/{generation.id}/banners.zip")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    names = zipfile.ZipFile(io.BytesIO(response.content)).namelist()
    assert names == ["adgen-post-overlay.jpg", "adgen-post-panel.jpg", "adgen-2gis-clean.jpg"]


def test_zip_not_ready(client, session_factory):
    generation = created_generation(submit(client), session_factory)
    assert client.get(f"/generations/{generation.id}/banners.zip").status_code == 404


def test_api_returns_banners(client, monkeypatch, session_factory):
    generation = run_pipeline(client, monkeypatch, session_factory)

    data = client.get(f"/api/generations/{generation.id}").json()

    assert data["status"] == "done"
    assert data["formats"] == ["post", "2gis"]
    assert data["scene_source"] == "fallback"
    assert [b["format"] for b in data["banners"]] == ["post", "post", "2gis"]


def test_sprint1_generation_without_banners_still_renders(client, session_factory):
    """Генерации Спринта 1 (только удаление фона) открываются без ошибок."""
    generation_id = uuid.uuid4()
    with session_factory() as db:
        db.add(
            Generation(
                id=generation_id,
                status=GenerationStatus.DONE,
                source_path="generations/x/source.jpg",
                cutout_path="generations/x/cutout.png",
            )
        )
        db.commit()
    response = client.get(f"/generations/{generation_id}")
    assert response.status_code == 200
    assert "Товар без фона" in response.text


def test_banner_model_labels():
    banner = Banner(format="2gis", variant="clean", image_path="generations/x/2gis-clean.jpg")
    assert banner.image_url == "/media/generations/x/2gis-clean.jpg"
    assert banner.download_name == "adgen-2gis-clean.jpg"
    assert banner.aspect_ratio == "1200 / 624"


def test_unknown_generation_returns_404(client):
    assert client.get(f"/generations/{uuid.uuid4()}").status_code == 404

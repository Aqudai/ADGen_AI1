"""Загрузка фото, задача Celery и страница результата."""

import uuid

from PIL import Image

from app import tasks
from app.models import Generation, GenerationStatus
from app.routers import generations
from tests.conftest import make_image_bytes


class FakeTask:
    """Заменяет задачу Celery: запоминает вызовы вместо отправки в Redis."""

    def __init__(self):
        self.calls = []

    def delay(self, *args):
        self.calls.append(args)


def fake_remove_background(image: Image.Image) -> Image.Image:
    """Вместо нейросети: делает картинку полупрозрачной. Быстро и без модели."""
    cutout = image.convert("RGBA")
    cutout.putalpha(128)
    return cutout


def upload(client, data: bytes, filename="photo.jpg", content_type="image/jpeg"):
    return client.post(
        "/generations",
        files={"photo": (filename, data, content_type)},
        follow_redirects=False,
    )


def create_generation(client, monkeypatch, session_factory) -> Generation:
    """Загружает фото через форму и возвращает созданную запись."""
    monkeypatch.setattr(generations, "process_generation", FakeTask())
    response = upload(client, make_image_bytes())
    generation_id = uuid.UUID(response.headers["location"].rsplit("/", 1)[1])
    with session_factory() as db:
        return db.get(Generation, generation_id)


def test_create_page(client):
    response = client.get("/create")
    assert response.status_code == 200
    assert 'enctype="multipart/form-data"' in response.text


def test_upload_saves_photo_and_queues_task(client, monkeypatch, session_factory, media_dir):
    fake_task = FakeTask()
    monkeypatch.setattr(generations, "process_generation", fake_task)

    response = upload(client, make_image_bytes())

    assert response.status_code == 303
    generation_id = response.headers["location"].rsplit("/", 1)[1]
    assert fake_task.calls == [(generation_id,)]
    with session_factory() as db:
        generation = db.get(Generation, uuid.UUID(generation_id))
    assert generation.status == GenerationStatus.PENDING
    assert (media_dir / generation.source_path).exists()


def test_upload_without_file_shows_error(client):
    response = client.post("/generations", data={})
    assert response.status_code == 400
    assert "Выберите фото" in response.text


def test_upload_of_non_image_shows_error(client):
    response = upload(client, b"not an image at all", filename="virus.jpg")
    assert response.status_code == 400
    assert "Не удалось открыть" in response.text


def test_upload_too_large_file_shows_error(client, monkeypatch):
    monkeypatch.setattr(generations.settings, "max_upload_mb", 0)
    response = upload(client, make_image_bytes())
    assert response.status_code == 400
    assert "Файл больше" in response.text


def test_task_removes_background(client, monkeypatch, session_factory, media_dir):
    generation = create_generation(client, monkeypatch, session_factory)
    monkeypatch.setattr(tasks, "remove_background", fake_remove_background)

    tasks.process_generation(str(generation.id))  # вызываем задачу напрямую, без очереди

    with session_factory() as db:
        generation = db.get(Generation, generation.id)
    assert generation.status == GenerationStatus.DONE
    cutout = Image.open(media_dir / generation.cutout_path)
    assert cutout.mode == "RGBA"


def test_task_failure_is_saved(client, monkeypatch, session_factory):
    generation = create_generation(client, monkeypatch, session_factory)

    def broken_remove_background(image):
        raise RuntimeError("модель сломалась")

    monkeypatch.setattr(tasks, "remove_background", broken_remove_background)

    tasks.process_generation(str(generation.id))

    with session_factory() as db:
        generation = db.get(Generation, generation.id)
    assert generation.status == GenerationStatus.FAILED
    assert "Не удалось обработать" in generation.error_message


def test_status_partial_polls_while_in_progress(client, monkeypatch, session_factory):
    generation = create_generation(client, monkeypatch, session_factory)
    response = client.get(f"/generations/{generation.id}/status")
    assert response.status_code == 200
    assert 'hx-trigger="every 1s"' in response.text
    assert "В очереди" in response.text


def test_status_partial_shows_result_when_done(client, monkeypatch, session_factory):
    generation = create_generation(client, monkeypatch, session_factory)
    monkeypatch.setattr(tasks, "remove_background", fake_remove_background)
    tasks.process_generation(str(generation.id))

    response = client.get(f"/generations/{generation.id}/status")

    assert "hx-trigger" not in response.text  # опрос прекращается
    assert "Скачать PNG" in response.text
    assert f"/media/generations/{generation.id}/cutout.png" in response.text


def test_generation_page_and_api(client, monkeypatch, session_factory):
    generation = create_generation(client, monkeypatch, session_factory)

    page = client.get(f"/generations/{generation.id}")
    assert page.status_code == 200
    assert "Удаление фона" in page.text

    api = client.get(f"/api/generations/{generation.id}")
    assert api.status_code == 200
    assert api.json()["status"] == "pending"
    assert api.json()["cutout_url"] is None


def test_unknown_generation_returns_404(client):
    assert client.get(f"/generations/{uuid.uuid4()}").status_code == 404

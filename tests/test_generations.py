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


@pytest.fixture
def client(user_client):
    """Все тесты этого файла — от имени вошедшего пользователя."""
    return user_client


@pytest.fixture(autouse=True)
def no_ai(monkeypatch):
    """В тестах пайплайна нейросеть для сцены выключена (её вызов проверяется в test_scene.py)."""
    monkeypatch.setattr(settings, "image_provider", "none")


def fake_remove_background(image: Image.Image) -> Image.Image:
    """Вместо нейросети: делает картинку полупрозрачной. Быстро и без модели."""
    cutout = image.convert("RGBA")
    cutout.putalpha(128)
    return cutout


def submit(client, photo=None, **fields):
    data = {"promo_text": PROMO, "design_request": "", "formats": ["post", "2gis"]} | fields
    files = {}
    if photo is not False:
        files["photo"] = ("photo.jpg", photo or make_image_bytes(), "image/jpeg")
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
    assert 'name="design_request"' in response.text
    assert "Ярко и дерзко" in response.text  # подсказки к пожеланию
    assert response.text.count('name="formats"') == 3


def test_submit_saves_generation_and_queues_task(client, session_factory, media_dir, fake_queue):
    response = submit(client)

    assert response.status_code == 303
    generation = created_generation(response, session_factory)
    assert fake_queue.calls == [(str(generation.id),)]
    assert generation.status == GenerationStatus.PENDING
    assert generation.promo_text == PROMO
    assert generation.design_request is None
    assert generation.formats == ["post", "2gis"]
    assert (media_dir / generation.source_path).exists()
    assert generation.logo_path is None


@pytest.mark.parametrize(
    ("fields", "message"),
    [
        ({"promo_text": "   "}, "Введите текст акции"),
        ({"promo_text": "А" * 121}, "длиннее 120 символов"),
        ({"design_request": "я" * 201}, "длиннее 200 символов"),
        ({"formats": []}, "хотя бы один формат"),
        ({"formats": ["post", "billboard"]}, "Неизвестный формат"),
        ({"photo": False}, "Выберите фото"),
        ({"photo": b"not an image"}, "Не удалось открыть файл"),
    ],
)
def test_form_errors(client, fake_queue, fields, message):
    response = submit(client, **fields)
    assert response.status_code == 400
    assert message in response.text
    assert fake_queue.calls == []  # ничего не поставили в очередь


def test_form_keeps_entered_text_after_error(client):
    response = submit(client, formats=[], promo_text="Мой текст акции", design_request="уютно")
    assert "Мой текст акции" in response.text
    assert "уютно" in response.text


def test_photo_too_large(client, monkeypatch):
    monkeypatch.setattr(settings, "max_upload_mb", 0)
    response = submit(client)
    assert response.status_code == 400
    assert "Фото больше" in response.text


def test_pipeline_creates_banners(client, monkeypatch, session_factory, media_dir):
    generation = run_pipeline(
        client,
        monkeypatch,
        session_factory,
        formats=["post", "story", "2gis"],
        design_request="Премиум, шрифт с засечками",
    )

    assert generation.status == GenerationStatus.DONE
    assert generation.step is None
    assert generation.scene_source is None  # нейросеть не подключена — сцены нет
    assert generation.design["mood"] == "premium"
    assert generation.design["font"] == "serif"
    # 4 варианта дизайна × 3 формата
    assert len(generation.banners) == 12
    variants = list(dict.fromkeys(b.variant for b in generation.banners))
    assert variants[0] == "luxe-1" and len(variants) == 4
    for banner in generation.banners:
        image = Image.open(media_dir / banner.image_path)
        assert (
            image.size
            == {"post": (1080, 1080), "story": (1080, 1920), "2gis": (1200, 624)}[banner.format]
        )
    assert (media_dir / generation.cutout_path).exists()
    assert generation.scene_path is None


def test_pipeline_uses_brand_profile(client, monkeypatch, session_factory, media_dir):
    """Логотип и цвета из профиля бренда попадают в генерацию (как снимок)."""
    logo = make_image_bytes((300, 100), color=(0, 0, 255, 0), fmt="PNG", mode="RGBA")
    client.post(
        "/profile",
        data={"business_name": "Кофейня", "primary_color": "#112233", "secondary_color": "#AA0000"},
        files={"logo": ("logo.png", logo, "image/png")},
    )
    generation = run_pipeline(client, monkeypatch, session_factory, formats=["post"])

    assert generation.status == GenerationStatus.DONE
    assert generation.brand_name == "Кофейня"
    assert generation.primary_color == "#112233"
    assert generation.secondary_color == "#AA0000"
    saved_logo = Image.open(media_dir / generation.logo_path)
    assert saved_logo.mode == "RGBA" and saved_logo.getpixel((5, 5))[3] == 0  # прозрачность цела


def test_pipeline_with_name_instead_of_logo(client, monkeypatch, session_factory):
    client.post(
        "/profile",
        data={
            "business_name": "Суши Хаус",
            "primary_color": "#E8743B",
            "secondary_color": "#E11D48",
        },
    )
    generation = run_pipeline(client, monkeypatch, session_factory, formats=["post"])
    assert generation.status == GenerationStatus.DONE
    assert generation.logo_path is None and generation.brand_name == "Суши Хаус"


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
    assert "Собираем варианты дизайна" in response.text


def test_status_partial_shows_gallery_when_done(client, monkeypatch, session_factory):
    generation = run_pipeline(client, monkeypatch, session_factory)

    response = client.get(f"/generations/{generation.id}/status")

    assert "hx-trigger" not in response.text  # опрос прекращается
    assert "Скачать все баннеры" in response.text
    assert "Вариант 1 ·" in response.text
    assert "Как мы поняли пожелание" in response.text
    assert response.text.count('download="adgen-post-') == 4
    assert "для блока «Скидки»" in response.text


def test_banner_content_fields_saved_and_used(client, monkeypatch, session_factory, media_dir):
    client.post(
        "/profile",
        data={
            "business_name": "Кофейня",
            "primary_color": "#112233",
            "secondary_color": "#AA0000",
            "contacts": "+7 777 000 00 00",
            "qr_url": "wa.me/77770000000",
        },
    )
    generation = run_pipeline(
        client,
        monkeypatch,
        session_factory,
        formats=["post"],
        text_kz="Жаңа өнім",
        price="1990",
        old_price="2490",
        deadline="до пятницы",
        cta="Ждём вас!",
    )
    assert generation.status == GenerationStatus.DONE
    assert generation.price == "1\u00a0990\u00a0₸"
    assert generation.text_kz == "Жаңа өнім"
    assert generation.contacts == "+7 777 000 00 00"
    assert generation.qr_url == "https://wa.me/77770000000"


def test_create_page_has_ready_texts_and_extra_fields(client):
    page = client.get("/create").text
    assert "Второй десерт в подарок" in page
    assert 'name="text_kz"' in page and 'name="price"' in page and 'name="cta"' in page


def test_ai_scene_variant_added_when_enabled(client, monkeypatch, session_factory):
    """С ключом Hugging Face добавляется пятый вариант — товар на сцене от нейросети."""
    from app import tasks

    monkeypatch.setattr(settings, "image_provider", "huggingface")
    monkeypatch.setattr(settings, "hf_token", "hf_test")
    monkeypatch.setattr(
        tasks, "generate_ai_scene", lambda style: (Image.new("RGB", (64, 64), "tan"), None)
    )
    generation = run_pipeline(client, monkeypatch, session_factory, formats=["post"])
    assert [b.variant for b in generation.banners][-1] == "ai"
    assert len(generation.banners) == 5
    assert generation.scene_source == SceneSource.AI


def test_ai_scene_failure_is_explained(client, monkeypatch, session_factory):
    from app import tasks

    monkeypatch.setattr(settings, "image_provider", "huggingface")
    monkeypatch.setattr(settings, "hf_token", "hf_test")
    monkeypatch.setattr(tasks, "generate_ai_scene", lambda style: (None, "закончились кредиты"))
    generation = run_pipeline(client, monkeypatch, session_factory, formats=["post"])

    assert len(generation.banners) == 4  # основные варианты на месте
    page = client.get(f"/generations/{generation.id}").text
    assert "Вариант со сценой от нейросети пропущен: закончились кредиты" in page


def test_zip_contains_all_banners(client, monkeypatch, session_factory):
    generation = run_pipeline(client, monkeypatch, session_factory)

    response = client.get(f"/generations/{generation.id}/banners.zip")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    names = zipfile.ZipFile(io.BytesIO(response.content)).namelist()
    assert len(names) == 8  # 4 варианта × (пост + 2GIS)
    assert all(name.startswith("adgen-") and name.endswith(".jpg") for name in names)


def test_zip_not_ready(client, session_factory):
    generation = created_generation(submit(client), session_factory)
    assert client.get(f"/generations/{generation.id}/banners.zip").status_code == 404


def test_api_returns_banners(client, monkeypatch, session_factory):
    generation = run_pipeline(client, monkeypatch, session_factory)

    data = client.get(f"/api/generations/{generation.id}").json()

    assert data["status"] == "done"
    assert data["formats"] == ["post", "2gis"]
    assert data["scene_source"] is None
    assert [b["format"] for b in data["banners"]][:2] == ["post", "2gis"]


def test_sprint1_generation_without_banners_still_renders(client, session_factory):
    """Генерации Спринта 1 (только удаление фона) открываются без ошибок."""
    generation_id = uuid.uuid4()
    with session_factory() as db:
        db.add(
            Generation(
                id=generation_id,
                user_id=1,
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
    assert Banner(format="post", variant="pop-1", image_path="x").variant_label == "Яркий"
    assert Banner(format="post", variant="ai", image_path="x").variant_label == "Сцена от нейросети"
    banner = Banner(format="2gis", variant="clean", image_path="generations/x/2gis-clean.jpg")
    assert banner.variant_label == "Без текста, для блока «Скидки»"  # старая генерация
    assert banner.image_url == "/media/generations/x/2gis-clean.jpg"
    assert banner.download_name == "adgen-2gis-clean.jpg"
    assert banner.aspect_ratio == "1200 / 624"


def test_unknown_generation_returns_404(client):
    assert client.get(f"/generations/{uuid.uuid4()}").status_code == 404

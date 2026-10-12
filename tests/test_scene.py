"""Сцена: запасной фон и вызов нейросети через Hugging Face.

Hugging Face в тестах не вызываем. Вместо него — локальный HTTP-сервер, который
отвечает как сервис генерации (картинкой или ошибкой). Если вместо имени модели
передать адрес, библиотека huggingface_hub отправляет запрос прямо на него —
так проверяется настоящий код библиотеки и наша обработка ошибок.
"""

import io
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from PIL import Image

from app.config import settings
from app.models import SceneSource
from app.services import huggingface, scene
from app.services.fallback_scene import SCENE_SIZE, draw_fallback_scene
from app.services.presets import STYLES


class FakeGenerator(BaseHTTPRequestHandler):
    """Отвечает кодом из server.status; на 200 — PNG-картинкой."""

    def do_POST(self):
        self.rfile.read(int(self.headers.get("Content-Length", 0)))
        if self.server.delay:
            time.sleep(self.server.delay)
        if self.server.status == 200:
            buffer = io.BytesIO()
            Image.new("RGB", (64, 64), "orange").save(buffer, format="PNG")
            body, content_type = buffer.getvalue(), "image/png"
        else:
            body, content_type = b'{"error": "fake error"}', "application/json"
        self.send_response(self.server.status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):  # не засорять вывод тестов
        pass


@pytest.fixture
def fake_hf(monkeypatch):
    server = ThreadingHTTPServer(("127.0.0.1", 0), FakeGenerator)
    server.status, server.delay = 200, 0
    threading.Thread(target=server.serve_forever, daemon=True).start()
    monkeypatch.setattr(settings, "hf_model", f"http://127.0.0.1:{server.server_port}/generate")
    monkeypatch.setattr(settings, "hf_token", "hf_test")
    yield server
    server.shutdown()


@pytest.mark.parametrize("style", list(STYLES))
def test_fallback_scene_is_square_and_repeatable(style):
    first = draw_fallback_scene(style, seed=7)
    assert first.size == (SCENE_SIZE, SCENE_SIZE)
    assert first.tobytes() == draw_fallback_scene(style, seed=7).tobytes()  # один seed — один фон


def test_without_token_scene_is_drawn_without_ai(monkeypatch):
    monkeypatch.setattr(settings, "hf_token", "")
    result = scene.generate_scene("cozy", seed=1)
    assert result.source == SceneSource.FALLBACK
    assert "HF_TOKEN" in result.note


def test_fallback_provider_skips_ai(monkeypatch, fake_hf):
    monkeypatch.setattr(settings, "image_provider", "fallback")
    result = scene.generate_scene("minimal", seed=1)
    assert result.source == SceneSource.FALLBACK
    assert result.note is None  # выбрано сознательно — предупреждать не о чем


def test_ai_scene(fake_hf):
    result = scene.generate_scene("festive", seed=1)
    assert result.source == SceneSource.AI
    assert result.note is None
    assert result.image.mode == "RGB"


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (401, "не принял ключ"),
        (403, "не принял ключ"),
        (402, "закончились кредиты"),
        (429, "подождать"),
        (500, "временно недоступен"),
    ],
)
def test_ai_errors_fall_back_with_reason(fake_hf, status, expected):
    fake_hf.status = status
    result = scene.generate_scene("cozy", seed=1)
    assert result.source == SceneSource.FALLBACK
    assert expected in result.note


def test_ai_timeout_falls_back(fake_hf, monkeypatch):
    fake_hf.delay = 2
    monkeypatch.setattr(settings, "hf_timeout", 0.5)
    result = scene.generate_scene("cozy", seed=1)
    assert result.source == SceneSource.FALLBACK
    assert "не ответила вовремя" in result.note


def test_not_an_image_response_falls_back(fake_hf, monkeypatch):
    """Сервис ответил 200, но прислал не картинку (например, HTML-страницу ошибки)."""

    def broken_png(self):
        self.send_response(200)
        self.send_header("Content-Type", "image/png")
        self.send_header("Content-Length", "9")
        self.end_headers()
        self.wfile.write(b"<html/>!!")

    monkeypatch.setattr(FakeGenerator, "do_POST", broken_png)
    result = scene.generate_scene("cozy", seed=1)
    assert result.source == SceneSource.FALLBACK
    assert "не картинку" in result.note


def test_unexpected_library_error_falls_back(monkeypatch):
    """Даже непредвиденная ошибка внутри библиотеки не роняет генерацию."""

    class BrokenClient:
        def __init__(self, **kwargs):
            pass

        def text_to_image(self, *args, **kwargs):
            raise StopIteration  # так ведёт себя huggingface_hub при provider=auto и пустом списке

        def close(self):
            pass

    monkeypatch.setattr(settings, "hf_token", "hf_test")
    monkeypatch.setattr(huggingface, "InferenceClient", BrokenClient)
    result = scene.generate_scene("cozy", seed=1)
    assert result.source == SceneSource.FALLBACK
    assert result.note == "нейросеть недоступна"


def test_no_connection_falls_back(monkeypatch):
    monkeypatch.setattr(settings, "hf_token", "hf_test")
    monkeypatch.setattr(settings, "hf_model", "http://127.0.0.1:9/generate")  # порт закрыт
    with pytest.raises(huggingface.SceneGenerationError, match="нет связи"):
        huggingface.text_to_image("prompt", 64)

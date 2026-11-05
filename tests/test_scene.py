"""Необязательная сцена от нейросети через Hugging Face.

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
from app.services import huggingface, scene


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


def test_ai_scene_needs_token(monkeypatch):
    monkeypatch.setattr(settings, "hf_token", "")
    assert not scene.ai_scene_enabled()
    monkeypatch.setattr(settings, "hf_token", "hf_test")
    assert scene.ai_scene_enabled()
    monkeypatch.setattr(settings, "image_provider", "none")
    assert not scene.ai_scene_enabled()


def test_ai_scene(fake_hf):
    image, note = scene.generate_ai_scene("festive")
    assert note is None
    assert image.mode == "RGB"


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
    image, note = scene.generate_ai_scene("cozy")
    assert image is None
    assert expected in note


def test_ai_timeout_falls_back(fake_hf, monkeypatch):
    fake_hf.delay = 2
    monkeypatch.setattr(settings, "hf_timeout", 0.5)
    image, note = scene.generate_ai_scene("cozy")
    assert image is None
    assert "не ответила вовремя" in note


def test_not_an_image_response_falls_back(fake_hf, monkeypatch):
    """Сервис ответил 200, но прислал не картинку (например, HTML-страницу ошибки)."""

    def broken_png(self):
        self.send_response(200)
        self.send_header("Content-Type", "image/png")
        self.send_header("Content-Length", "9")
        self.end_headers()
        self.wfile.write(b"<html/>!!")

    monkeypatch.setattr(FakeGenerator, "do_POST", broken_png)
    image, note = scene.generate_ai_scene("cozy")
    assert image is None
    assert "не картинку" in note


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
    image, note = scene.generate_ai_scene("cozy")
    assert image is None
    assert note == "нейросеть недоступна"


def test_no_connection_falls_back(monkeypatch):
    monkeypatch.setattr(settings, "hf_token", "hf_test")
    monkeypatch.setattr(settings, "hf_model", "http://127.0.0.1:9/generate")  # порт закрыт
    with pytest.raises(huggingface.SceneGenerationError, match="нет связи"):
        huggingface.text_to_image("prompt", 64)

from io import BytesIO

import fakeredis
import pytest
from fastapi.testclient import TestClient

from backend.app.config import Settings
from backend.app.database import make_engine, make_session_factory
from backend.app.main import create_app
from backend.app.models import Base
from backend.app.observability import Metrics
from worker.consumer import Worker


class FakePredictor:
    version = "test-model-v1"
    sha256 = "a" * 64

    def __init__(self):
        self.calls = 0
        self.failure = False

    def predict(self, path):
        self.calls += 1
        if self.failure:
            raise RuntimeError("private input must not be exposed")
        assert path.is_file()
        return [{"class_id": 1, "label": "goldfish", "confidence": 0.9}]


@pytest.fixture
def image_bytes():
    from PIL import Image

    def make(fmt="PNG", size=(32, 24)):
        output = BytesIO()
        Image.new("RGB", size, color=(200, 80, 40)).save(output, format=fmt)
        return output.getvalue()
    return make


@pytest.fixture
def context(tmp_path):
    settings = Settings(_env_file=None, database_url=f"sqlite:///{tmp_path / 'test.db'}",
                        upload_dir=tmp_path / "uploads", max_upload_bytes=4096,
                        max_image_pixels=10000, job_lease_seconds=1)
    engine = make_engine(settings.database_url)
    Base.metadata.create_all(engine)
    sessions = make_session_factory(engine)
    redis = fakeredis.FakeRedis(decode_responses=True)
    predictor = FakePredictor()
    metrics = Metrics()
    app = create_app(settings, sessions, redis)
    worker = Worker(settings, sessions, redis, predictor, metrics)
    with TestClient(app) as client:
        yield {"client": client, "settings": settings, "sessions": sessions, "redis": redis,
               "predictor": predictor, "worker": worker, "metrics": metrics, "app": app}
    redis.close()
    engine.dispose()


def submit(context, data):
    response = context["client"].post("/jobs", files={"file": ("photo.png", data, "image/png")})
    assert response.status_code == 202, response.text
    return response.json()["job_id"]

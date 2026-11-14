"""Opt-in: PostgreSQL + Redis Streams + MobileNetV2 thật, namespace riêng cho mỗi lần chạy."""
import os
import time
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from redis import Redis
from sqlalchemy import text

from backend.app.config import Settings
from backend.app.database import make_engine, make_session_factory
from backend.app.main import create_app
from backend.app.models import Base, Job
from backend.app.observability import Metrics
from backend.app.queue import ensure_group
from worker.consumer import Worker
from worker.inference import MobileNetPredictor

pytestmark = [pytest.mark.integration, pytest.mark.skipif(
    os.getenv("RUN_INTEGRATION_TESTS") != "1",
    reason="Đặt RUN_INTEGRATION_TESTS=1 và chạy PostgreSQL/Redis để bật integration test.",
)]


@pytest.fixture
def real_context(tmp_path):
    schema = "test_" + uuid4().hex
    settings = Settings(
        _env_file=None,
        database_url=os.getenv("TEST_DATABASE_URL", "postgresql+psycopg://app:change_me@localhost:5432/ai_app"),
        redis_url=os.getenv("TEST_REDIS_URL", "redis://localhost:16379/15"),
        redis_stream=f"test:{schema}:jobs", redis_group=f"test:{schema}:workers",
        upload_dir=tmp_path / "uploads", job_lease_seconds=1,
    )
    raw_engine = make_engine(settings.database_url)
    with raw_engine.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = raw_engine.execution_options(schema_translate_map={None: schema})
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    try:
        Base.metadata.create_all(engine)
        sessions = make_session_factory(engine)
        predictor = MobileNetPredictor(settings)
        worker = Worker(settings, sessions, redis, predictor, Metrics())
        app = create_app(settings, sessions, redis)
        with TestClient(app) as client:
            yield settings, sessions, redis, worker, client
    finally:
        redis.delete(settings.redis_stream)
        redis.close()
        with raw_engine.begin() as connection:
            # Tên schema do fixture sinh, không lấy từ đầu vào bên ngoài.
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        raw_engine.dispose()


def test_postgres_redis_onnx_end_to_end(real_context, image_bytes):
    settings, sessions, redis, worker, client = real_context
    assert client.get("/ready").status_code == 200
    response = client.post("/jobs", files={"file": ("sample.png", image_bytes(), "image/png")})
    assert response.status_code == 202
    job_id = response.json()["job_id"]
    assert redis.xlen(settings.redis_stream) == 1
    worker.tick(block_ms=1)
    result = client.get(f"/jobs/{job_id}").json()
    assert result["status"] == "completed", result
    assert len(result["predictions"]) == 5
    assert result["model_sha256"] == settings.model_sha256
    assert result["model_version"] == settings.model_version
    with sessions() as session:
        assert session.get(Job, job_id).image_path is None
    assert redis.xpending(settings.redis_stream, settings.redis_group)["pending"] == 0
    assert not list(settings.upload_dir.glob("*"))


def test_real_redis_reclaims_crashed_consumer(real_context, image_bytes):
    settings, sessions, redis, worker, client = real_context
    response = client.post("/jobs", files={"file": ("sample.png", image_bytes(), "image/png")})
    job_id = response.json()["job_id"]
    ensure_group(redis, settings)
    messages = redis.xreadgroup(settings.redis_group, "dead-worker", {settings.redis_stream: ">"}, count=1)
    message_id = messages[0][1][0][0]
    with sessions.begin() as session:
        job = session.get(Job, job_id)
        job.status, job.lease_until, job.lease_token = "processing", time.time() - 2, "dead-owner"
    redis.xclaim(settings.redis_stream, settings.redis_group, "dead-worker", 0, [message_id], idle=2000)
    worker.tick(block_ms=1)
    assert client.get(f"/jobs/{job_id}").json()["status"] == "completed"

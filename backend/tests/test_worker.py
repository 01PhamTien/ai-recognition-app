import time
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from redis.exceptions import ConnectionError as RedisConnectionError

from backend.app.models import Job
from backend.app.queue import dispatch_pending, ensure_group
from backend.tests.conftest import submit
from worker.main import create_app


def test_full_job_flow_is_idempotent_and_deletes_image(context, image_bytes):
    job_id = submit(context, image_bytes())
    context["worker"].tick(block_ms=1)
    job = context["client"].get(f"/jobs/{job_id}").json()
    assert job["status"] == "completed"
    assert job["predictions"][0]["label"] == "goldfish"
    assert job["model_version"] == context["predictor"].version
    assert job["model_sha256"] == context["predictor"].sha256
    assert job["error"] is None
    assert not list(context["settings"].upload_dir.glob("*"))
    assert context["redis"].xpending(context["settings"].redis_stream, context["settings"].redis_group)["pending"] == 0
    assert context["worker"].process(job_id)
    assert context["predictor"].calls == 1


def test_inference_failure_is_persisted_and_acknowledged(context, image_bytes):
    job_id = submit(context, image_bytes())
    context["predictor"].failure = True
    context["worker"].tick(block_ms=1)
    result = context["client"].get(f"/jobs/{job_id}").json()
    assert result["status"] == "failed"
    assert result["predictions"] is None
    assert result["error"]["code"] == "inference_failed"
    assert "private" not in str(result)
    assert not list(context["settings"].upload_dir.glob("*"))


def test_crashed_consumer_message_and_expired_lease_are_reclaimed(context, image_bytes):
    settings, redis = context["settings"], context["redis"]
    job_id = submit(context, image_bytes())
    ensure_group(redis, settings)
    messages = redis.xreadgroup(settings.redis_group, "dead-worker", {settings.redis_stream: ">"}, count=1)
    message_id = messages[0][1][0][0]
    with context["sessions"].begin() as session:
        job = session.get(Job, job_id)
        job.status = "processing"
        job.lease_token = str(uuid4())
        job.lease_until = time.time() - 2
    redis.xclaim(settings.redis_stream, settings.redis_group, "dead-worker", 0, [message_id], idle=2000)
    context["worker"].tick(block_ms=1)
    assert context["client"].get(f"/jobs/{job_id}").json()["status"] == "completed"


def test_live_lease_prevents_duplicate_inference(context, image_bytes):
    job_id = submit(context, image_bytes())
    with context["sessions"].begin() as session:
        job = session.get(Job, job_id)
        job.status = "processing"
        job.lease_token = str(uuid4())
        job.lease_until = time.time() + 60
    assert context["worker"].process(job_id) is False
    assert context["predictor"].calls == 0


def test_lost_lease_cannot_overwrite_new_owner(context, image_bytes, monkeypatch):
    job_id = submit(context, image_bytes())
    def lose_lease(path):
        with context["sessions"].begin() as session:
            job = session.get(Job, job_id)
            job.lease_token = "new-owner"
        return [{"class_id": 1, "label": "test", "confidence": 0.5}]
    monkeypatch.setattr(context["predictor"], "predict", lose_lease)
    assert context["worker"].process(job_id) is False
    with context["sessions"]() as session:
        job = session.get(Job, job_id)
        assert job.status == "processing" and job.predictions is None


def test_redis_write_then_error_can_duplicate_message_safely(context, image_bytes, monkeypatch):
    original = context["redis"].xadd
    def ambiguous_write(*args, **kwargs):
        original(*args, **kwargs)
        raise RedisConnectionError("lost response")
    monkeypatch.setattr(context["redis"], "xadd", ambiguous_write)
    job_id = submit(context, image_bytes())
    monkeypatch.setattr(context["redis"], "xadd", original)
    assert dispatch_pending(context["sessions"], context["redis"], context["settings"]) == 1
    context["worker"].tick(block_ms=1)
    context["worker"].tick(block_ms=1)
    assert context["client"].get(f"/jobs/{job_id}").json()["status"] == "completed"
    assert context["predictor"].calls == 1


def test_invalid_and_missing_job_messages_can_be_acknowledged(context):
    assert context["worker"].process("invalid")
    assert context["worker"].process(None)
    assert context["worker"].process(str(uuid4()))


def test_worker_exposes_health_metrics_and_readiness(context):
    app = create_app(context["settings"], context["sessions"], context["redis"], context["predictor"], start_worker=False)
    with TestClient(app) as client:
        assert client.get("/health").json() == {"status": "ok"}
        assert client.get("/ready").status_code == 503
        assert client.get("/metrics").status_code == 200
        assert "recognition_jobs_total" in client.get("/metrics").text


def test_database_failure_leaves_message_pending_until_retry(context, image_bytes, monkeypatch):
    from sqlalchemy.exc import OperationalError
    settings, redis = context["settings"], context["redis"]
    job_id = submit(context, image_bytes())
    ensure_group(redis, settings)
    messages = redis.xreadgroup(settings.redis_group, "first-worker", {settings.redis_stream: ">"}, count=1)[0][1]
    original_begin = context["sessions"].begin
    original_predict = context["predictor"].predict

    def unavailable():
        raise OperationalError("db unavailable", {}, Exception())

    def fail_when_saving(path):
        predictions = original_predict(path)
        monkeypatch.setattr(context["sessions"], "begin", unavailable)
        return predictions

    monkeypatch.setattr(context["predictor"], "predict", fail_when_saving)
    with pytest.raises(OperationalError):
        context["worker"].handle(messages)
    assert redis.xpending(settings.redis_stream, settings.redis_group)["pending"] == 1
    monkeypatch.setattr(context["sessions"], "begin", original_begin)
    monkeypatch.setattr(context["predictor"], "predict", original_predict)
    with context["sessions"].begin() as session:
        session.get(Job, job_id).lease_until = time.time() - 2
    redis.xclaim(settings.redis_stream, settings.redis_group, "first-worker", 0, [messages[0][0]], idle=2000)
    context["worker"].tick(block_ms=1)
    assert context["client"].get(f"/jobs/{job_id}").json()["status"] == "completed"

from uuid import uuid4

import pytest
from redis.exceptions import ConnectionError as RedisConnectionError
from sqlalchemy import func, select

from backend.app.models import Job
from backend.tests.conftest import submit


def test_accepts_job_and_exposes_polling_contract(context, image_bytes):
    response = context["client"].post("/jobs", files={"file": ("photo.jpg", image_bytes("JPEG"), "image/jpeg")})
    assert response.status_code == 202
    accepted = response.json()
    assert accepted["status"] == "queued"
    assert response.headers["location"] == accepted["status_url"]
    job = context["client"].get(accepted["status_url"]).json()
    assert job["job_id"] == accepted["job_id"]
    assert job["status"] == "queued"
    assert job["predictions"] is None and job["error"] is None
    assert "image_path" not in job
    assert context["redis"].xlen(context["settings"].redis_stream) == 1


@pytest.mark.parametrize("filename,mime,data,status,code", [
    ("photo.gif", "image/gif", b"GIF89a", 415, "unsupported_media_type"),
    ("photo.txt", "image/png", b"hello", 415, "unsupported_media_type"),
    ("photo.png", "image/png", b"", 422, "empty_file"),
    ("photo.png", "image/png", b"not an image", 422, "invalid_image"),
    ("photo.png", "image/png", b"x" * 4097, 413, "file_too_large"),
])
def test_invalid_upload_never_creates_job(context, filename, mime, data, status, code):
    response = context["client"].post("/jobs", files={"file": (filename, data, mime)})
    assert response.status_code == status
    assert response.json()["error"]["code"] == code
    with context["sessions"]() as session:
        assert session.scalar(select(func.count()).select_from(Job)) == 0
    assert context["redis"].xlen(context["settings"].redis_stream) == 0


def test_rejects_spoofed_mime(context, image_bytes):
    response = context["client"].post("/jobs", files={"file": ("photo.jpg", image_bytes(), "image/jpeg")})
    assert response.status_code == 415


def test_rejects_excessive_pixels(context, image_bytes):
    response = context["client"].post("/jobs", files={"file": ("photo.png", image_bytes(size=(101, 100)), "image/png")})
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "image_too_large"


def test_rejects_corrupt_image(context, image_bytes):
    response = context["client"].post("/jobs", files={"file": ("photo.png", image_bytes()[:45], "image/png")})
    assert response.status_code == 422


def test_missing_file_unknown_and_malformed_job(context):
    client = context["client"]
    assert client.post("/jobs").status_code == 422
    response = client.get(f"/jobs/{uuid4()}")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "job_not_found"
    assert client.get("/jobs/not-a-uuid").status_code == 422


def test_multipart_body_limit_applies_without_content_length(context):
    boundary = b"--example\r\nContent-Disposition: form-data; name=\"file\"; filename=\"a.png\"\r\nContent-Type: image/png\r\n\r\n"
    def chunks():
        yield boundary
        for _ in range(80):
            yield b"x" * 1024
        yield b"\r\n--example--\r\n"
    response = context["client"].post("/jobs", content=chunks(), headers={"Content-Type": "multipart/form-data; boundary=example"})
    assert response.status_code == 413


def test_redis_outage_keeps_job_in_outbox(context, image_bytes, monkeypatch):
    original = context["redis"].xadd
    def unavailable(*args, **kwargs):
        raise RedisConnectionError("offline")
    monkeypatch.setattr(context["redis"], "xadd", unavailable)
    job_id = submit(context, image_bytes())
    with context["sessions"]() as session:
        job = session.get(Job, job_id)
        assert job.status == "queued" and not job.published
    monkeypatch.setattr(context["redis"], "xadd", original)
    context["worker"].tick(block_ms=1)
    assert context["client"].get(f"/jobs/{job_id}").json()["status"] == "completed"


def test_metrics_readiness_and_cors(context):
    client = context["client"]
    assert client.get("/ready").status_code == 200
    client.get(f"/jobs/{uuid4()}")
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]
    assert 'path="/jobs/{job_id}"' in response.text
    assert "http_request_duration_seconds" in response.text
    response = client.options("/jobs", headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST"})
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_readiness_reports_dependency_outage(context, monkeypatch):
    def unavailable():
        raise RedisConnectionError()
    monkeypatch.setattr(context["redis"], "ping", unavailable)
    assert context["client"].get("/health").status_code == 200
    response = context["client"].get("/ready")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "dependency_unavailable"


def test_db_failure_returns_503_and_removes_uploaded_file(context, image_bytes, monkeypatch):
    from sqlalchemy.exc import OperationalError
    def unavailable():
        raise OperationalError("private connection string", {}, Exception())
    monkeypatch.setattr(context["sessions"], "begin", unavailable)
    response = context["client"].post("/jobs", files={"file": ("photo.png", image_bytes(), "image/png")})
    assert response.status_code == 503
    assert "private" not in response.text
    assert not list(context["settings"].upload_dir.glob("*"))

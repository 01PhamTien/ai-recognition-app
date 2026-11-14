import logging
import time
from pathlib import Path
from threading import Event
from uuid import UUID, uuid4

from sqlalchemy import or_, select, update

from backend.app.models import Job, utcnow
from backend.app.queue import dispatch_pending, ensure_group

logger = logging.getLogger(__name__)


class Worker:
    def __init__(self, settings, sessions, redis, predictor, metrics):
        self.settings, self.sessions, self.redis = settings, sessions, redis
        self.predictor, self.metrics = predictor, metrics
        self.consumer = f"worker-{uuid4()}"
        self.stop = Event()
        self.last_success = 0.0
        self.claim_cursor = "0-0"

    def clean_files(self):
        with self.sessions.begin() as session:
            jobs = session.scalars(select(Job).where(
                Job.status.in_(["completed", "failed"]), Job.image_path.is_not(None),
            ).limit(100).with_for_update(skip_locked=True)).all()
            for job in jobs:
                try:
                    self.image_path(job.image_path).unlink(missing_ok=True)
                    job.image_path = None
                except OSError:
                    logger.warning("image_cleanup_deferred", extra={"job_id": job.id})

    def image_path(self, name: str) -> Path:
        root = self.settings.upload_dir.resolve()
        path = (root / name).resolve()
        if path.parent != root:
            raise ValueError("Đường dẫn ảnh không hợp lệ.")
        return path

    def process(self, job_id: str) -> bool:
        """True: có thể ACK. False: lease của worker khác còn hiệu lực."""
        try:
            job_id = str(UUID(job_id))
        except (ValueError, TypeError, AttributeError):
            logger.warning("invalid_queue_message")
            return True
        token, now = str(uuid4()), time.time()
        with self.sessions.begin() as session:
            job = session.get(Job, job_id)
            if job is None or job.status in ("completed", "failed"):
                return True
            claim = session.execute(
                update(Job).where(Job.id == job_id, or_(
                    Job.status == "queued",
                    (Job.status == "processing") & (Job.lease_until <= now),
                )).values(status="processing", lease_token=token,
                          lease_until=now + self.settings.job_lease_seconds, updated_at=utcnow())
            )
            if claim.rowcount != 1:
                return False
            image_name = job.image_path

        predictions, error = None, None
        try:
            with self.metrics.inference.time():
                predictions = self.predictor.predict(self.image_path(image_name))
        except Exception as exc:
            error = {"code": "inference_failed", "message": "Không thể nhận diện ảnh."}
            logger.error("inference_failed", extra={"job_id": job_id, "error_type": type(exc).__name__})
        status = "failed" if error else "completed"
        with self.sessions.begin() as session:
            result = session.execute(
                update(Job).where(Job.id == job_id, Job.lease_token == token).values(
                    status=status, predictions=predictions, error=error,
                    model_version=self.predictor.version, model_sha256=self.predictor.sha256,
                    lease_token=None, lease_until=None, updated_at=utcnow(),
                )
            )
            if result.rowcount != 1:
                return False
        self.metrics.jobs.labels(status).inc()
        logger.info("job_finished", extra={"job_id": job_id, "status": status})
        return True

    def handle(self, messages):
        for message_id, fields in messages:
            if self.stop.is_set():
                break
            if self.process(fields.get("job_id")):
                self.redis.xack(self.settings.redis_stream, self.settings.redis_group, message_id)
                # Một consumer group; chỉ xóa sau khi kết quả đã commit và ACK.
                self.redis.xdel(self.settings.redis_stream, message_id)
        self.clean_files()

    def tick(self, block_ms=1000):
        ensure_group(self.redis, self.settings)
        dispatch_pending(self.sessions, self.redis, self.settings)
        claimed = self.redis.xautoclaim(
            self.settings.redis_stream, self.settings.redis_group, self.consumer,
            min_idle_time=self.settings.job_lease_seconds * 1000,
            start_id=self.claim_cursor, count=10,
        )
        self.claim_cursor = claimed[0]
        self.handle(claimed[1])
        incoming = self.redis.xreadgroup(
            self.settings.redis_group, self.consumer,
            {self.settings.redis_stream: ">"}, count=1, block=block_ms,
        )
        for _, messages in incoming:
            self.handle(messages)
        self.clean_files()
        self.last_success = time.time()

    def run(self):
        logger.info("worker_started")
        while not self.stop.is_set():
            try:
                self.tick()
            except Exception as exc:
                self.last_success = 0
                logger.error("worker_retry", extra={"error_type": type(exc).__name__})
                self.stop.wait(2)
        logger.info("worker_stopped")

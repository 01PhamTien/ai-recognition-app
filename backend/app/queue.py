from redis.exceptions import ResponseError
from sqlalchemy import select

from backend.app.models import Job


def ensure_group(redis, settings) -> None:
    try:
        redis.xgroup_create(settings.redis_stream, settings.redis_group, id="0-0", mkstream=True)
    except ResponseError as exc:
        if "BUSYGROUP" not in str(exc):
            raise


def dispatch_pending(sessions, redis, settings, limit: int = 100) -> int:
    """Bảng jobs kiêm outbox; crash có thể phát trùng message nhưng không ghi đè kết quả."""
    count = 0
    with sessions.begin() as session:
        jobs = session.scalars(
            select(Job).where(Job.status == "queued", Job.published.is_(False))
            .order_by(Job.created_at).limit(limit).with_for_update(skip_locked=True)
        ).all()
        for job in jobs:
            redis.xadd(settings.redis_stream, {"job_id": job.id})
            job.published = True
            count += 1
    return count

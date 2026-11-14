import logging
from contextlib import asynccontextmanager
from uuid import UUID, uuid4

from fastapi import FastAPI, File, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from redis import Redis
from redis.exceptions import RedisError
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from backend.app.body_limit import UploadBodyLimit
from backend.app.config import Settings
from backend.app.database import make_engine, make_session_factory
from backend.app.errors import APIError
from backend.app.images import validate_image
from backend.app.models import Job
from backend.app.observability import Metrics, configure_logging, install_http_observability
from backend.app.queue import dispatch_pending
from backend.app.schemas import ErrorResponse, JobAccepted, JobResponse

logger = logging.getLogger(__name__)


def create_app(settings=None, sessions=None, redis_client=None) -> FastAPI:
    settings = settings or Settings()
    configure_logging("api", settings.log_level)
    engine = None if sessions is not None else make_engine(settings.database_url)
    sessions = sessions if sessions is not None else make_session_factory(engine)
    redis = redis_client if redis_client is not None else Redis.from_url(
        settings.redis_url, decode_responses=True, socket_connect_timeout=3, socket_timeout=5,
    )

    @asynccontextmanager
    async def lifespan(app):
        yield
        if redis_client is None:
            redis.close()
        if engine is not None:
            engine.dispose()

    app = FastAPI(title="AI Recognition API", version="1.0.0", lifespan=lifespan)
    metrics = Metrics()
    app.state.settings, app.state.sessions, app.state.redis = settings, sessions, redis
    app.state.metrics = metrics
    app.add_middleware(UploadBodyLimit, max_bytes=settings.max_upload_bytes + 64 * 1024)
    install_http_observability(app, metrics)
    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins,
                       allow_methods=["GET", "POST"], allow_headers=["Content-Type"],
                       expose_headers=["Location", "X-Request-ID"])

    @app.exception_handler(APIError)
    async def api_error(request, exc):
        return JSONResponse({"error": {"code": exc.code, "message": exc.message}}, status_code=exc.status)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        return JSONResponse({"error": {"code": "validation_error", "message": "Thiếu file hoặc tham số không hợp lệ."}}, status_code=422)

    @app.exception_handler(HTTPException)
    async def http_error(request, exc):
        return JSONResponse({"error": {"code": "http_error", "message": str(exc.detail)}}, status_code=exc.status_code)

    @app.exception_handler(Exception)
    async def unexpected_error(request, exc):
        logger.error("request_failed", extra={"error_type": type(exc).__name__})
        return JSONResponse({"error": {"code": "internal_error", "message": "Lỗi nội bộ dịch vụ."}}, status_code=500)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/ready", responses={503: {"model": ErrorResponse}})
    def ready():
        try:
            with sessions() as session:
                session.execute(select(Job.id).limit(1))
            redis.ping()
        except (SQLAlchemyError, RedisError):
            raise APIError(503, "dependency_unavailable", "PostgreSQL hoặc Redis chưa sẵn sàng.") from None
        return {"status": "ready"}

    @app.get("/metrics", include_in_schema=False)
    def prometheus_metrics():
        return metrics.response()

    def persist_job(data, width, height, extension, content_type):
        job_id = str(uuid4())
        path = settings.upload_dir.resolve() / f"{job_id}{extension}"
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            with sessions.begin() as session:
                session.add(Job(id=job_id, image_path=path.name, content_type=content_type,
                                size_bytes=len(data), width=width, height=height))
        except (OSError, SQLAlchemyError):
            try:
                path.unlink(missing_ok=True)
            except OSError:
                logger.warning("image_cleanup_deferred", extra={"job_id": job_id})
            raise APIError(503, "storage_unavailable", "Chưa thể lưu tác vụ; vui lòng thử lại.") from None
        try:
            dispatch_pending(sessions, redis, settings)
        except (RedisError, SQLAlchemyError):
            logger.warning("job_waiting_for_dispatch", extra={"job_id": job_id})
        logger.info("job_accepted", extra={"job_id": job_id})
        return job_id

    errors = {code: {"model": ErrorResponse} for code in (413, 415, 422, 503)}

    @app.post("/jobs", status_code=202, response_model=JobAccepted, responses=errors)
    async def upload_image(file: UploadFile = File(...)):
        try:
            data = await file.read(settings.max_upload_bytes + 1)
            width, height, extension = await run_in_threadpool(
                validate_image, data, file.filename or "", file.content_type or "", settings,
            )
            job_id = await run_in_threadpool(persist_job, data, width, height, extension, file.content_type)
        finally:
            await file.close()
        url = f"/jobs/{job_id}"
        return JSONResponse(JobAccepted(job_id=job_id, status_url=url).model_dump(mode="json"),
                            status_code=202, headers={"Location": url})

    @app.get("/jobs/{job_id}", response_model=JobResponse,
             responses={404: {"model": ErrorResponse}, 422: {"model": ErrorResponse}, 503: {"model": ErrorResponse}})
    def get_job(job_id: UUID):
        try:
            with sessions() as session:
                job = session.get(Job, str(job_id))
                if job is None:
                    raise APIError(404, "job_not_found", "Không tìm thấy tác vụ.")
                return JobResponse(job_id=job.id, status=job.status, predictions=job.predictions,
                                   error=job.error, model_version=job.model_version, model_sha256=job.model_sha256,
                                   created_at=job.created_at, updated_at=job.updated_at)
        except SQLAlchemyError:
            raise APIError(503, "database_unavailable", "PostgreSQL chưa sẵn sàng.") from None

    return app


app = create_app()

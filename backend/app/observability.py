import json
import logging
import os
import sys
from datetime import datetime, timezone
from time import perf_counter

from prometheus_client import CollectorRegistry, Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response


class JSONFormatter(logging.Formatter):
    def format(self, record):
        data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "service": getattr(record, "service", os.getenv("SERVICE_NAME", "api")),
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key in ("request_id", "method", "path", "status", "duration_seconds", "job_id", "error_type"):
            if hasattr(record, key):
                data[key] = getattr(record, key)
        # Không ghi nội dung exception có thể chứa URL kết nối hoặc dữ liệu người dùng.
        if record.exc_info:
            data["error_type"] = record.exc_info[0].__name__
        return json.dumps(data, ensure_ascii=False)


def configure_logging(service: str, level: str) -> None:
    os.environ["SERVICE_NAME"] = service
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())
    logging.basicConfig(level=level.upper(), handlers=[handler], force=True)
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        log = logging.getLogger(name)
        log.handlers.clear()
        log.propagate = True
    logging.getLogger("uvicorn.access").disabled = True


class Metrics:
    def __init__(self):
        self.registry = CollectorRegistry()
        self.requests = Counter("http_requests_total", "HTTP requests", ["method", "path", "status"], registry=self.registry)
        self.duration = Histogram("http_request_duration_seconds", "HTTP latency", ["method", "path"], registry=self.registry)
        self.jobs = Counter("recognition_jobs_total", "Worker outcomes", ["status"], registry=self.registry)
        self.inference = Histogram("recognition_inference_seconds", "Model inference latency", registry=self.registry)

    def response(self):
        return Response(generate_latest(self.registry), headers={"Content-Type": CONTENT_TYPE_LATEST})


def install_http_observability(app, metrics):
    import uuid
    logger = logging.getLogger("http")

    @app.middleware("http")
    async def observe(request, call_next):
        request_id = str(uuid.uuid4())
        start = perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            elapsed = perf_counter() - start
            route = request.scope.get("route")
            path = getattr(route, "path", "unmatched")
            metrics.requests.labels(request.method, path, str(status)).inc()
            metrics.duration.labels(request.method, path).observe(elapsed)
            logger.info("http_request", extra={"request_id": request_id, "method": request.method,
                        "path": path, "status": status, "duration_seconds": elapsed})

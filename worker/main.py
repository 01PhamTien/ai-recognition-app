import time
from contextlib import asynccontextmanager
from threading import Thread

from fastapi import FastAPI
from redis import Redis
from sqlalchemy import text
from starlette.concurrency import run_in_threadpool
from starlette.responses import JSONResponse

from backend.app.config import Settings
from backend.app.database import make_engine, make_session_factory
from backend.app.observability import Metrics, configure_logging, install_http_observability
from worker.consumer import Worker
from worker.inference import MobileNetPredictor


def create_app(settings=None, sessions=None, redis_client=None, predictor=None, start_worker=True):
    settings = settings or Settings()
    configure_logging("worker", settings.log_level)
    metrics = Metrics()
    engine = None if sessions is not None else make_engine(settings.database_url)
    sessions = sessions if sessions is not None else make_session_factory(engine)
    redis = redis_client if redis_client is not None else Redis.from_url(
        settings.redis_url, decode_responses=True, socket_connect_timeout=3, socket_timeout=5,
    )
    state = {"worker": None, "thread": None}

    @asynccontextmanager
    async def lifespan(app):
        model = predictor if predictor is not None else await run_in_threadpool(MobileNetPredictor, settings)
        worker = Worker(settings, sessions, redis, model, metrics)
        state["worker"] = worker
        thread = Thread(target=worker.run, daemon=True, name="recognition-consumer")
        state["thread"] = thread
        if start_worker:
            thread.start()
        try:
            yield
        finally:
            worker.stop.set()
            if start_worker:
                await run_in_threadpool(thread.join, 10)
            if not thread.is_alive():
                if redis_client is None:
                    redis.close()
                if engine is not None:
                    engine.dispose()

    app = FastAPI(title="AI Recognition Worker", lifespan=lifespan)
    app.state.metrics = metrics
    app.state.worker_state = state
    install_http_observability(app, metrics)

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.get("/ready")
    def ready():
        worker, thread = state["worker"], state["thread"]
        if worker is None or not thread.is_alive() or time.time() - worker.last_success > 15:
            return JSONResponse({"error": {"code": "worker_unavailable", "message": "Worker chưa sẵn sàng."}}, status_code=503)
        try:
            with sessions() as session:
                session.execute(text("SELECT 1"))
            redis.ping()
        except Exception:
            return JSONResponse({"error": {"code": "dependency_unavailable", "message": "PostgreSQL hoặc Redis chưa sẵn sàng."}}, status_code=503)
        return {"status": "ready"}

    @app.get("/metrics", include_in_schema=False)
    def prometheus_metrics():
        return metrics.response()

    return app


app = create_app()

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 SERVICE_NAME=worker
WORKDIR /app
COPY backend/requirements.txt backend/requirements.txt
COPY worker/requirements.txt worker/requirements.txt
RUN pip install --no-cache-dir -r worker/requirements.txt
COPY backend backend
COPY worker worker
COPY scripts scripts
COPY models/manifest.json models/manifest.json
RUN useradd --uid 10001 --create-home appuser \
    && mkdir -p /app/data/uploads /app/models /app/model-assets && chown -R appuser:appuser /app
USER appuser
EXPOSE 8001
CMD ["python", "-m", "uvicorn", "worker.main:app", "--host", "0.0.0.0", "--port", "8001", "--no-access-log"]

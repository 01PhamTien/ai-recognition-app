from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://app:change_me@localhost:5432/ai_app"
    redis_url: str = "redis://localhost:16379/0"
    redis_stream: str = "recognition:jobs"
    redis_group: str = "recognition-workers"
    upload_dir: Path = Path("data/uploads")
    max_upload_bytes: int = Field(default=5 * 1024 * 1024, gt=0)
    max_image_pixels: int = Field(default=20_000_000, gt=0)
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    model_path: Path = Path("models/mobilenetv2-7.onnx")
    labels_path: Path = Path("models/synset.txt")
    model_version: str = "mobilenetv2-7-v1"
    model_sha256: str = "c1c513582d56afceff8516c73804e484c81c6a830712ab6d682253f4a3cd042f"
    labels_sha256: str = "acf75ef0abe89694b19056e0796401068b459c457baa30335f240c7692857355"
    top_k: int = Field(default=5, ge=1, le=1000)
    job_lease_seconds: int = Field(default=300, ge=1)
    log_level: str = "INFO"

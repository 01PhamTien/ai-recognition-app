from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorDetail


class Prediction(BaseModel):
    class_id: int
    label: str
    confidence: float = Field(ge=0, le=1)


class JobAccepted(BaseModel):
    job_id: UUID
    status: Literal["queued"] = "queued"
    status_url: str


class JobResponse(BaseModel):
    job_id: UUID
    status: Literal["queued", "processing", "completed", "failed"]
    predictions: list[Prediction] | None
    error: ErrorDetail | None
    model_version: str | None
    model_sha256: str | None
    created_at: datetime
    updated_at: datetime

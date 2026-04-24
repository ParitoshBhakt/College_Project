from datetime import datetime

from pydantic import BaseModel


class DetectionResult(BaseModel):
    face_id: int
    emotion: str
    confidence: float
    message: str
    suggestion: str
    wellness_score: float
    gradcam_base64: str


class PredictResponse(BaseModel):
    request_id: str
    detections: list[DetectionResult]
    model_metrics: dict[str, float]


class HistoryItem(BaseModel):
    id: int
    emotion: str
    confidence: float
    suggestion: str
    created_at: datetime


class HistoryResponse(BaseModel):
    records: list[HistoryItem]
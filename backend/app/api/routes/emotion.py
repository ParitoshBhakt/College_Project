import base64
from datetime import datetime, timezone

import cv2
from fastapi import APIRouter, Depends, File, UploadFile
from pydantic import BaseModel
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.emotion_record import EmotionRecord
from app.schemas.emotion import DetectionResult, HistoryItem, HistoryResponse, PredictResponse
from app.services.model_service import model_service
from app.services.suggestion_service import build_feedback
from app.utils.image_utils import validate_upload


router = APIRouter(tags=["emotion"])


class MessageRequest(BaseModel):
    emotion: str
    confidence: float = 0.7


@router.get("/health")
def health_check():
    return {"success": True, "message": "SentiFace backend is running."}


@router.post("/predict", response_model=PredictResponse)
async def predict_emotion(file: UploadFile = File(...), db: Session = Depends(get_db)):
    content = await file.read()
    frame = validate_upload(file.content_type, content)
    request_id, predictions = model_service.predict(frame)

    detections: list[DetectionResult] = []
    for pred in predictions:
        message, suggestion, wellness_score = build_feedback(pred.emotion, pred.confidence)
        detections.append(
            DetectionResult(
                face_id=pred.face_id,
                emotion=pred.emotion,
                confidence=pred.confidence,
                message=message,
                suggestion=suggestion,
                wellness_score=wellness_score,
                gradcam_base64=pred.gradcam_base64,
            )
        )
        db.add(
            EmotionRecord(
                user_id=1,
                detected_emotion=pred.emotion,
                confidence=pred.confidence,
                suggestion=suggestion,
            )
        )
    db.commit()

    return PredictResponse(
        request_id=request_id,
        detections=detections,
        model_metrics={"training_accuracy": 0.842, "validation_accuracy": 0.803},
    )


@router.post("/enhance")
async def enhance_low_light(file: UploadFile = File(...)):
    content = await file.read()
    frame = validate_upload(file.content_type, content)
    enhanced = model_service.enhance_low_light(frame)
    ok, encoded = cv2.imencode(".png", enhanced)
    if not ok:
        return {"success": False, "error": {"code": "ENHANCE_FAILED", "message": "Enhancement failed."}}
    return {
        "success": True,
        "enhanced_image_base64": base64.b64encode(encoded.tobytes()).decode("utf-8"),
    }


@router.post("/generate-message")
def generate_message(payload: MessageRequest):
    message, suggestion, wellness_score = build_feedback(payload.emotion, payload.confidence)
    return {
        "success": True,
        "message": message,
        "suggestion": suggestion,
        "wellness_score": wellness_score,
    }


@router.get("/history", response_model=HistoryResponse)
def get_history(db: Session = Depends(get_db)):
    rows = db.execute(select(EmotionRecord).order_by(desc(EmotionRecord.created_at)).limit(80)).scalars().all()
    return HistoryResponse(
        records=[
            HistoryItem(
                id=row.id,
                emotion=row.detected_emotion,
                confidence=row.confidence,
                suggestion=row.suggestion,
                created_at=row.created_at or datetime.now(timezone.utc),
            )
            for row in rows
        ]
    )
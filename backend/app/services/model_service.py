import base64
import io
import os
import uuid
from dataclasses import dataclass

import cv2
import numpy as np
import torch
import torchvision.transforms as T
from PIL import Image
from torch import nn
from torchvision.models import resnet18

from app.core.config import settings
from app.utils.exceptions import SentiFaceError


EMOTIONS = ["angry", "disgust", "fear", "happy", "sad", "surprise", "neutral"]


@dataclass
class FaceResult:
    face_id: int
    emotion: str
    confidence: float
    gradcam_base64: str


class EmotionModelService:
    def __init__(self) -> None:
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model = self._load_model()
        self.face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
        self.transform = T.Compose(
            [
                T.Resize((48, 48)),
                T.Grayscale(num_output_channels=3),
                T.ToTensor(),
                T.Normalize(mean=[0.5, 0.5, 0.5], std=[0.5, 0.5, 0.5]),
            ]
        )

    def _load_model(self) -> nn.Module:
        model = resnet18(weights=None)
        model.fc = nn.Linear(model.fc.in_features, len(EMOTIONS))
        if os.path.exists(settings.model_path):
            state = torch.load(settings.model_path, map_location="cpu")
            model.load_state_dict(state)
        model.eval()
        model.to(self.device)
        return model

    def detect_faces(self, frame: np.ndarray) -> list[np.ndarray]:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        boxes = self.face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))
        if len(boxes) == 0:
            raise SentiFaceError("NO_FACE_DETECTED", "No face detected in the image.", 422)
        faces: list[np.ndarray] = []
        for box in boxes:
            x, y, w, h = [int(v) for v in box]
            crop = frame[y : y + h, x : x + w]
            if crop.size:
                faces.append(crop)
        if not faces:
            raise SentiFaceError("NO_FACE_DETECTED", "No valid face region found.", 422)
        return faces

    def predict(self, frame: np.ndarray) -> tuple[str, list[FaceResult]]:
        request_id = str(uuid.uuid4())
        faces = self.detect_faces(frame)
        results: list[FaceResult] = []
        for index, face in enumerate(faces, start=1):
            pil_face = Image.fromarray(cv2.cvtColor(face, cv2.COLOR_BGR2RGB))
            tensor = self.transform(pil_face).unsqueeze(0).to(self.device)
            with torch.no_grad():
                logits = self.model(tensor)
                probs = torch.softmax(logits, dim=1).cpu().numpy()[0]
            cls = int(np.argmax(probs))
            results.append(
                FaceResult(
                    face_id=index,
                    emotion=EMOTIONS[cls],
                    confidence=float(probs[cls]),
                    gradcam_base64=self._dummy_gradcam(face),
                )
            )
        return request_id, results

    def enhance_low_light(self, frame: np.ndarray) -> np.ndarray:
        ycrcb = cv2.cvtColor(frame, cv2.COLOR_BGR2YCrCb)
        y, cr, cb = cv2.split(ycrcb)
        y_eq = cv2.equalizeHist(y)
        merged = cv2.merge([y_eq, cr, cb])
        return cv2.cvtColor(merged, cv2.COLOR_YCrCb2BGR)

    def _dummy_gradcam(self, face: np.ndarray) -> str:
        heat = cv2.applyColorMap(cv2.resize(face, (160, 160)), cv2.COLORMAP_JET)
        ok, encoded = cv2.imencode(".png", heat)
        if not ok:
            return ""
        return base64.b64encode(io.BytesIO(encoded.tobytes()).getvalue()).decode("utf-8")


model_service = EmotionModelService()
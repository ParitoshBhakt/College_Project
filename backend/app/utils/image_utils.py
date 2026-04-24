import io

import cv2
import numpy as np
from PIL import Image

from app.utils.exceptions import SentiFaceError


ALLOWED_TYPES = {"image/png", "image/jpeg", "image/jpg"}


def validate_upload(content_type: str | None, content: bytes) -> np.ndarray:
    if content_type not in ALLOWED_TYPES:
        raise SentiFaceError("INVALID_FILE_FORMAT", "Invalid file format. Use PNG or JPG.", 422)

    try:
        image = Image.open(io.BytesIO(content)).convert("RGB")
    except Exception as exc:  # pragma: no cover - defensive branch
        raise SentiFaceError("INVALID_IMAGE", "Unable to parse image bytes.", 422) from exc

    frame = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
    if frame.shape[0] < 32 or frame.shape[1] < 32:
        raise SentiFaceError("LOW_RESOLUTION", "Image resolution too low for emotion detection.", 422)
    if estimate_blur(frame) < 55.0:
        raise SentiFaceError("BLURRY_IMAGE", "Image appears blurry. Upload a clearer frame.", 422)
    return frame


def estimate_blur(frame: np.ndarray) -> float:
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    return cv2.Laplacian(gray, cv2.CV_64F).var()
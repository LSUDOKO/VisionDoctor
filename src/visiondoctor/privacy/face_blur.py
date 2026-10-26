"""Blur faces on every evidence image before it is stored or shown (docs/03 §7).

YuNet (OpenCV zoo, ``cv2.FaceDetectorYN``) finds faces; each box (padded 20%) is mosaicked and Gaussian-blurred.
No identification, no embeddings, no face recognition anywhere in VisionDoctor. If the model
file is missing we fail closed: the whole image is pixelated rather than stored unblurred.
"""

from __future__ import annotations

import threading
from pathlib import Path

import cv2
import numpy as np

from visiondoctor.config import get_settings
from visiondoctor.observability.metrics import timer

_lock = threading.Lock()
_det: cv2.FaceDetectorYN | None = None


def _detector(w: int, h: int) -> cv2.FaceDetectorYN | None:
    global _det
    path = Path(get_settings().models_dir) / "yunet.onnx"
    if not path.exists():
        return None
    if _det is None:
        _det = cv2.FaceDetectorYN.create(str(path), "", (w, h), 0.6, 0.3, 5000)
    _det.setInputSize((w, h))
    return _det


def detect_faces(img: np.ndarray) -> np.ndarray:
    h, w = img.shape[:2]
    with _lock:
        det = _detector(w, h)
        if det is None:
            raise FileNotFoundError("yunet.onnx missing")
        with timer("yunet_detect"):
            _, faces = det.detect(img)
    return np.zeros((0, 15)) if faces is None else faces


def blur_faces(img: np.ndarray, pad: float = 0.2, passes: int = 3) -> tuple[np.ndarray, int]:
    """Return (blurred copy, faces blurred). Re-detects after each pass (faces hidden behind
    stronger detections surface once those are gone). Fails closed without the model."""
    out = img.copy()
    total = 0
    for _ in range(passes):
        try:
            faces = detect_faces(out)
        except FileNotFoundError:
            h, w = img.shape[:2]
            small = cv2.resize(img, (max(w // 16, 1), max(h // 16, 1)), interpolation=cv2.INTER_AREA)
            return cv2.resize(small, (w, h), interpolation=cv2.INTER_NEAREST), -1
        if len(faces) == 0:
            break
        _blur_boxes(out, faces, pad)
        total += len(faces)
    return out, total


def _blur_boxes(out: np.ndarray, faces: np.ndarray, pad: float) -> None:
    H, W = out.shape[:2]
    for f in faces:
        x, y, w, h = f[:4]
        x0, y0 = int(max(x - pad * w, 0)), int(max(y - pad * h, 0))
        x1, y1 = int(min(x + w * (1 + pad), W)), int(min(y + h * (1 + pad), H))
        if x1 > x0 and y1 > y0:
            roi = out[y0:y1, x0:x1]
            # Coarse mosaic then blur: irreversible and no longer detectable as a face.
            mosaic = cv2.resize(cv2.resize(roi, (5, 5), interpolation=cv2.INTER_AREA), roi.shape[1::-1],
                                interpolation=cv2.INTER_NEAREST)
            k = max(int(max(w, h) / 2) | 1, 15)
            out[y0:y1, x0:x1] = cv2.GaussianBlur(mosaic, (k, k), 0)

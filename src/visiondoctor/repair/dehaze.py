"""Dark-channel-prior dehazing (He et al. 2009) with a box-filter guided filter (no contrib)."""

from __future__ import annotations

import cv2
import numpy as np

from visiondoctor.health.features import dark_channel
from visiondoctor.observability.metrics import timed

PATCH = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 15))


def guided_filter(guide: np.ndarray, src: np.ndarray, r: int = 40, eps: float = 1e-3) -> np.ndarray:
    k = (2 * r + 1, 2 * r + 1)
    mean_i = cv2.boxFilter(guide, -1, k)
    mean_p = cv2.boxFilter(src, -1, k)
    cov_ip = cv2.boxFilter(guide * src, -1, k) - mean_i * mean_p
    var_i = cv2.boxFilter(guide * guide, -1, k) - mean_i * mean_i
    a = cov_ip / (var_i + eps)
    b = mean_p - a * mean_i
    return np.asarray(cv2.boxFilter(a, -1, k) * guide + cv2.boxFilter(b, -1, k))


def airlight(img: np.ndarray, dc: np.ndarray) -> np.ndarray:
    n = max(int(dc.size * 0.001), 1)
    idx = np.argpartition(dc.ravel(), -n)[-n:]
    return np.asarray(img.reshape(-1, 3)[idx].astype(np.float64).max(axis=0))


@timed("dehaze")
def apply(frame: np.ndarray, omega: float = 0.9, t0: float = 0.1) -> np.ndarray:
    img = frame.astype(np.float32) / 255.0
    A = airlight(frame, dark_channel(frame, PATCH)).astype(np.float32) / 255.0
    norm = (img / np.maximum(A, 1e-3) * 255).clip(0, 255).astype(np.uint8)
    t = 1.0 - omega * dark_channel(norm, PATCH).astype(np.float32) / 255.0
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255.0
    t = guided_filter(gray, t)
    J = (img - A) / np.maximum(t, t0)[..., None] + A
    return np.asarray((J * 255).clip(0, 255).astype(np.uint8))

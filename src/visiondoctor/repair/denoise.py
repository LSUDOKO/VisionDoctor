"""Non-local-means denoising (cv2.fastNlMeansDenoisingColored)."""

from __future__ import annotations

import cv2
import numpy as np

from visiondoctor.observability.metrics import timed


def h_for(sigma: float) -> float:
    return float(min(max(1.3 * sigma, 3.0), 15.0))


@timed("fastNlMeansDenoisingColored")
def apply(frame: np.ndarray, h: float) -> np.ndarray:
    return cv2.fastNlMeansDenoisingColored(frame, None, h, h, 7, 21)

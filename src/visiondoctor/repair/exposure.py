"""Exposure fix: gain + gamma LUT toward the reference luminance, optional CLAHE on Lab L.

Sensor gain/iris faults are linear, so the primary correction is a gain ``alpha``; ``gamma``
handles residual tone-curve mismatch. Both are applied in one ``cv2.LUT``.
"""

from __future__ import annotations

import cv2
import numpy as np

from visiondoctor.observability.metrics import timed


def gain_for(cur_lum: float, ref_lum: float) -> float:
    return float(max(ref_lum, 1.0) / max(cur_lum, 1.0))


def lut(alpha: float, gamma: float) -> np.ndarray:
    x = np.clip(alpha * np.arange(256) / 255.0, 0, 1)
    return np.asarray(np.clip(255.0 * x**gamma, 0, 255).astype(np.uint8))


@timed("exposure_fix")
def apply(frame: np.ndarray, alpha: float, gamma: float = 1.0, clahe: bool = False, clip_limit: float = 2.0) -> np.ndarray:
    out = cv2.LUT(frame, lut(alpha, gamma))
    if clahe:
        lab = cv2.cvtColor(out, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        l = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=(8, 8)).apply(l)
        out = cv2.cvtColor(cv2.merge([l, a, b]), cv2.COLOR_LAB2BGR)
    return out

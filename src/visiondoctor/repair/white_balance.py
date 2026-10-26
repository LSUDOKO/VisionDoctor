"""White balance: per-channel gains restoring the reference's grey balance (no xphoto/contrib).

Plain grey-world assumes the scene averages to grey; for a fixed camera we know the scene's own
healthy balance, so gains map the current channel ratios back to the reference's.
"""

from __future__ import annotations

import cv2
import numpy as np

from visiondoctor.observability.metrics import timed


def gains_for(cur: np.ndarray, ref_bgr_mean: tuple[float, float, float]) -> list[float]:
    b, g, r, _ = cv2.mean(cur)
    cm = np.array([b, g, r]) + 1e-6
    rm = np.array(ref_bgr_mean) + 1e-6
    gains = (rm / rm.mean()) / (cm / cm.mean())
    return [float(x) for x in gains]


@timed("white_balance")
def apply(frame: np.ndarray, gains: list[float]) -> np.ndarray:
    ch = cv2.split(frame)
    out = [cv2.multiply(c, np.array([gn]), dtype=cv2.CV_8U) for c, gn in zip(ch, gains, strict=True)]
    return cv2.merge(out)

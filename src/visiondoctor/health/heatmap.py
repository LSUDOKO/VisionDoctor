"""Tile-wise quality map (1 = healthy) and its rendering for UI/evidence images."""

from __future__ import annotations

import cv2
import numpy as np

from visiondoctor.health.checks.base import ScanContext


def quality_map(ctx: ScanContext) -> np.ndarray:
    sharp = np.clip(ctx.tile_ratio("sharp_n"), 0, 1)
    edge = np.clip(ctx.tile_ratio("edge"), 0, 1)
    con = np.clip(ctx.tile_ratio("contrast"), 0, 1)
    textured = np.minimum(np.minimum(sharp, edge), con)
    lum_dev = np.abs(ctx.tiles["lum"] - ctx.bucket.tile_mean["lum"]) / 100.0
    flat = np.clip(1.0 - lum_dev, 0, 1)
    q = np.where(ctx.textured, textured, flat)
    return np.asarray(q, dtype=np.float32)


def render(frame: np.ndarray, q: np.ndarray, alpha: float = 0.45) -> np.ndarray:
    """Overlay the quality map (VIRIDIS; dark = degraded) on a BGR frame."""
    h, w = frame.shape[:2]
    big = cv2.resize((q * 255).astype(np.uint8), (w, h), interpolation=cv2.INTER_NEAREST)
    color = cv2.applyColorMap(big, cv2.COLORMAP_VIRIDIS)
    return cv2.addWeighted(frame, 1 - alpha, color, alpha, 0)

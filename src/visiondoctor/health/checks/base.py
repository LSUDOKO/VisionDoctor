"""Scan context shared by all checks: reference bucket, burst frames, cached features, camera state."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from functools import cached_property

import cv2
import numpy as np

from visiondoctor.health.features import TILE_METRICS, FrameFeatures
from visiondoctor.health.reference import RefBucket, Reference
from visiondoctor.health.types import CheckResult


@dataclass
class CameraState:
    """Per-camera memory that persists across scans (MOG2, freeze timer, …)."""

    mog2: cv2.BackgroundSubtractor = field(
        default_factory=lambda: cv2.createBackgroundSubtractorMOG2(history=500, detectShadows=False)
    )
    static_fg: np.ndarray | None = None  # running AND of foreground masks (uint8 tile grid)
    static_fg_scans: int = 0
    static_fg_since: float | None = None
    smudge_hist: list[np.ndarray] = field(default_factory=list)  # last scans' smudged tiles
    frozen_since: float | None = None
    last_thumb: str | None = None


@dataclass
class ScanContext:
    reference: Reference
    bucket_name: str
    bucket: RefBucket
    frames: list[np.ndarray]  # BGR at reference size, oldest → newest
    feats: list[FrameFeatures]
    state: CameraState
    now: float = field(default_factory=time.time)
    grid: int = 8
    results: dict[str, CheckResult] = field(default_factory=dict)  # earlier checks in this scan

    def sev(self, name: str) -> int:
        r = self.results.get(name)
        return r.severity if r else 0

    @cached_property
    def glob(self) -> dict[str, float]:
        """Median over the burst of every global metric (robust to a passing car)."""
        keys = self.feats[0].glob.keys()
        return {k: float(np.median([f.glob[k] for f in self.feats])) for k in keys}

    @cached_property
    def tiles(self) -> dict[str, np.ndarray]:
        return {m: np.median(np.stack([f.tiles[m] for f in self.feats]), axis=0) for m in TILE_METRICS}

    @cached_property
    def textured(self) -> np.ndarray:
        """Tiles whose reference has enough structure to judge sharpness/edges."""
        edge = self.bucket.tile_mean["edge"]
        return edge > max(0.01, 0.15 * float(np.median(edge)))

    @cached_property
    def static_tiles(self) -> np.ndarray:
        """Tiles that were mostly static during calibration (no traffic/pedestrians)."""
        g = self.grid
        frac = cv2.resize(self.bucket.static_mask, (g, g), interpolation=cv2.INTER_AREA) / 255.0
        return np.asarray(frac > 0.6)

    def ratio(self, key: str) -> float:
        ref = self.bucket.glob_mean[key]
        return self.glob[key] / ref if abs(ref) > 1e-9 else 1.0

    def lum_ratio_pct(self, q: float) -> float:
        """Percentile of per-tile luminance ratio: uniform for gain, skewed for local light."""
        r = self.tiles["lum"] / np.maximum(self.bucket.tile_mean["lum"], 5.0)
        return float(np.percentile(r, q))

    def tile_ratio(self, metric: str, cur: np.ndarray | None = None) -> np.ndarray:
        c = self.tiles[metric] if cur is None else cur
        return np.asarray(c / np.maximum(self.bucket.tile_mean[metric], 1e-6))

    def tile_z_drop(self, metric: str, cur: np.ndarray, floor_rel: float = 0.1) -> np.ndarray:
        mu, sd = self.bucket.tile_mean[metric], self.bucket.tile_std[metric]
        return np.asarray((mu - cur) / np.maximum(sd, floor_rel * np.abs(mu) + 1e-6))

    def tiles_to_bboxes(self, mask: np.ndarray) -> list[list[int]]:
        """Tile mask → pixel bounding boxes via findContours (TRUCO in OpenCV 5)."""
        h, w = self.frames[-1].shape[:2]
        big = cv2.resize(mask.astype(np.uint8) * 255, (w, h), interpolation=cv2.INTER_NEAREST)
        contours, _ = cv2.findContours(big, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        boxes = [list(cv2.boundingRect(c)) for c in contours]
        return sorted(boxes, key=lambda b: -b[2] * b[3])[:5]

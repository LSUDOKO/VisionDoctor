"""Per-camera reference ("what healthy looks like"), learned from a clean calibration window.

docs/03 §2: background median, static-region keypoints, per-tile and global metric baselines,
activity level, split into day/night luminance buckets. Slow EMA update only while healthy.
"""

from __future__ import annotations

import io
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from visiondoctor.health.features import (
    TILE_METRICS,
    FrameFeatures,
    compute_features,
    resize_to_width,
    temporal_sigma,
)
from visiondoctor.observability.metrics import timer

ORB_FEATURES = 3000
MIN_BUCKET_FRAMES = 10
STATIC_STD_MAX = 10.0


def orb() -> cv2.ORB:
    return cv2.ORB_create(nfeatures=ORB_FEATURES)


@dataclass
class RefBucket:
    background: np.ndarray  # BGR uint8 median
    static_mask: np.ndarray  # uint8 0/255
    kp_pts: np.ndarray  # (N,2) float32
    descriptors: np.ndarray  # (N,32) uint8
    tile_mean: dict[str, np.ndarray]
    tile_std: dict[str, np.ndarray]
    glob_mean: dict[str, float]
    glob_std: dict[str, float]
    activity: float
    n_frames: int


@dataclass
class Reference:
    camera_id: str
    width: int
    height: int
    buckets: dict[str, RefBucket]
    split_lum: float  # median-V threshold between night and day
    version: int = 1
    created_at: float = field(default_factory=time.time)
    detector_baseline: dict[str, float] = field(default_factory=dict)

    def bucket_for(self, lum_median: float) -> tuple[str, RefBucket]:
        if "night" in self.buckets and lum_median < self.split_lum:
            return "night", self.buckets["night"]
        return "day", self.buckets["day"]

    def prepare(self, img: np.ndarray) -> np.ndarray:
        """Bring a frame to the reference working size."""
        out = resize_to_width(img, self.width)
        if out.shape[0] != self.height:
            out = cv2.resize(out, (self.width, self.height), interpolation=cv2.INTER_AREA)
        return out

    # ---- persistence -------------------------------------------------------------------
    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        arrays: dict[str, np.ndarray] = {}
        meta: dict[str, Any] = {
            "camera_id": self.camera_id,
            "width": self.width,
            "height": self.height,
            "split_lum": self.split_lum,
            "version": self.version,
            "created_at": self.created_at,
            "detector_baseline": self.detector_baseline,
            "buckets": {},
        }
        for name, b in self.buckets.items():
            arrays[f"{name}.background"] = b.background
            arrays[f"{name}.static_mask"] = b.static_mask
            arrays[f"{name}.kp_pts"] = b.kp_pts
            arrays[f"{name}.descriptors"] = b.descriptors
            for m in TILE_METRICS:
                arrays[f"{name}.tm.{m}"] = b.tile_mean[m]
                arrays[f"{name}.ts.{m}"] = b.tile_std[m]
            meta["buckets"][name] = {
                "glob_mean": b.glob_mean,
                "glob_std": b.glob_std,
                "activity": b.activity,
                "n_frames": b.n_frames,
            }
        buf = io.BytesIO()
        np.savez_compressed(buf, **arrays)
        path.with_suffix(".npz").write_bytes(buf.getvalue())
        path.with_suffix(".json").write_text(json.dumps(meta, indent=1))

    @classmethod
    def load(cls, path: Path) -> Reference:
        meta = json.loads(path.with_suffix(".json").read_text())
        arr = np.load(path.with_suffix(".npz"))
        buckets = {}
        for name, bm in meta["buckets"].items():
            buckets[name] = RefBucket(
                background=arr[f"{name}.background"],
                static_mask=arr[f"{name}.static_mask"],
                kp_pts=arr[f"{name}.kp_pts"],
                descriptors=arr[f"{name}.descriptors"],
                tile_mean={m: arr[f"{name}.tm.{m}"] for m in TILE_METRICS},
                tile_std={m: arr[f"{name}.ts.{m}"] for m in TILE_METRICS},
                glob_mean=bm["glob_mean"],
                glob_std=bm["glob_std"],
                activity=bm["activity"],
                n_frames=bm["n_frames"],
            )
        return cls(
            camera_id=meta["camera_id"],
            width=meta["width"],
            height=meta["height"],
            buckets=buckets,
            split_lum=meta["split_lum"],
            version=meta["version"],
            created_at=meta["created_at"],
            detector_baseline=meta.get("detector_baseline", {}),
        )

    # ---- slow update -------------------------------------------------------------------
    def ema_update(self, feats: FrameFeatures, alpha: float = 0.02) -> None:
        """Nudge baselines toward a frame from a camera that has stayed healthy (docs/03 §2.4)."""
        _, b = self.bucket_for(feats.glob["lum_median"])
        for m in TILE_METRICS:
            b.tile_mean[m] = (1 - alpha) * b.tile_mean[m] + alpha * feats.tiles[m]
        for k, v in feats.glob.items():
            if k in b.glob_mean:
                b.glob_mean[k] = (1 - alpha) * b.glob_mean[k] + alpha * v
        self.version += 1


def _learn_bucket(frames: list[np.ndarray], feats: list[FrameFeatures]) -> RefBucket:
    stack = np.stack(frames[:30])
    with timer("median"):
        background = np.median(stack, axis=0).astype(np.uint8)
    grays = np.stack([f.gray for f in feats[:30]]).astype(np.float32)
    tstd = grays.std(axis=0)
    static = (tstd < STATIC_STD_MAX).astype(np.uint8) * 255
    static = cv2.erode(static, np.ones((5, 5), np.uint8))
    bg_gray = cv2.cvtColor(background, cv2.COLOR_BGR2GRAY)
    with timer("orb_detect"):
        kps, des = orb().detectAndCompute(bg_gray, static)
    if des is None:
        des = np.zeros((0, 32), np.uint8)
    pts = np.float32([k.pt for k in kps]).reshape(-1, 2)

    tile_mean, tile_std = {}, {}
    for m in TILE_METRICS:
        s = np.stack([f.tiles[m] for f in feats])
        tile_mean[m] = s.mean(axis=0)
        tile_std[m] = s.std(axis=0)
    keys = feats[0].glob.keys()
    glob_mean = {k: float(np.mean([f.glob[k] for f in feats])) for k in keys}
    glob_std = {k: float(np.std([f.glob[k] for f in feats])) for k in keys}
    nt = [temporal_sigma([a.gray, b.gray]) for a, b in zip(feats, feats[1:], strict=False)]
    glob_mean["noise_t"], glob_std["noise_t"] = float(np.median(nt)), float(np.std(nt))
    diffs = [float(cv2.absdiff(a.gray, b.gray).mean()) for a, b in zip(feats, feats[1:], strict=False)]
    return RefBucket(
        background=background,
        static_mask=static,
        kp_pts=pts,
        descriptors=des,
        tile_mean=tile_mean,
        tile_std=tile_std,
        glob_mean=glob_mean,
        glob_std=glob_std,
        activity=float(np.mean(diffs)) if diffs else 0.0,
        n_frames=len(frames),
    )


def learn_reference(camera_id: str, frames: list[np.ndarray], width: int = 960, grid: int = 8) -> Reference:
    """Learn a reference from clean calibration frames (BGR, any size)."""
    if len(frames) < 5:
        raise ValueError("need at least 5 calibration frames")
    prepared = [resize_to_width(f, min(width, f.shape[1])) for f in frames]
    h, w = prepared[0].shape[:2]
    prepared = [p if p.shape[:2] == (h, w) else cv2.resize(p, (w, h)) for p in prepared]
    feats = [compute_features(p, grid) for p in prepared]
    lums = np.array([f.glob["lum_median"] for f in feats])
    split = float(np.median(lums))
    day_idx = [i for i, v in enumerate(lums) if v >= split]
    night_idx = [i for i, v in enumerate(lums) if v < split]
    # Only split when the two halves are genuinely different lighting regimes.
    two_regimes = (
        len(night_idx) >= MIN_BUCKET_FRAMES
        and len(day_idx) >= MIN_BUCKET_FRAMES
        and np.mean(lums[day_idx]) - np.mean(lums[night_idx]) > 40
    )
    buckets: dict[str, RefBucket] = {}
    if two_regimes:
        buckets["day"] = _learn_bucket([prepared[i] for i in day_idx], [feats[i] for i in day_idx])
        buckets["night"] = _learn_bucket([prepared[i] for i in night_idx], [feats[i] for i in night_idx])
    else:
        buckets["day"] = _learn_bucket(prepared, feats)
        split = -1.0
    return Reference(camera_id=camera_id, width=w, height=h, buckets=buckets, split_lum=split)

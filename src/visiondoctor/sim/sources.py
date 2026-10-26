"""Camera sources: video files (MOT17 sequence videos, OpenCV vtest) and MOT17 ground truth."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from visiondoctor.config import get_settings

VIDEOS = {
    "MOT17-02": "MOT17-02.webm",
    "MOT17-04": "MOT17-04.webm",
    "MOT17-09": "MOT17-09.webm",
    "vtest": "vtest.avi",
}
MOT_SCALE = 0.5  # sequence videos are 960×540; labels are in 1920×1080 pixels


def video_path(name: str) -> Path:
    return get_settings().data_dir / "videos" / VIDEOS.get(name, name)


def available() -> list[str]:
    return [n for n in VIDEOS if video_path(n).exists()]


def read_frames(name: str, indices: list[int] | None = None, limit: int | None = None) -> dict[int, np.ndarray]:
    """Decode a video sequentially and keep the requested frame indices (or the first ``limit``)."""
    cap = cv2.VideoCapture(str(video_path(name)))
    want = set(indices) if indices is not None else None
    last = max(want) if want else (limit or 10**9) - 1
    out: dict[int, np.ndarray] = {}
    i = 0
    while i <= last:
        ok, f = cap.read()
        if not ok:
            break
        if want is None or i in want:
            out[i] = f
        i += 1
    cap.release()
    return out


def frame_count(name: str) -> int:
    cap = cv2.VideoCapture(str(video_path(name)))
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.release()
    return n


def mot17_gt(name: str, min_visibility: float = 0.25) -> dict[int, np.ndarray] | None:
    """Pedestrian boxes per 0-based frame index, scaled to video pixels; None if not MOT17."""
    if not name.startswith("MOT17"):
        return None
    p = get_settings().data_dir / "mot17" / "train" / f"{name}-SDP" / "gt" / "gt.txt"
    if not p.exists():
        return None
    a = np.loadtxt(p, delimiter=",")
    keep = (a[:, 6] == 1) & (a[:, 7] == 1) & (a[:, 8] >= min_visibility)
    a = a[keep]
    out: dict[int, np.ndarray] = {}
    for fr in np.unique(a[:, 0]).astype(int):
        r = a[a[:, 0] == fr]
        boxes = np.stack([r[:, 2], r[:, 3], r[:, 2] + r[:, 4], r[:, 3] + r[:, 5]], 1) * MOT_SCALE
        out[fr - 1] = boxes
    return out

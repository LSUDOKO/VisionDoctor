"""Shared helpers for eval scripts: cached references/bursts, bootstrap CIs, JSON output."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
RESULTS = ROOT / "results"
CACHE = RESULTS / "impact" / "cache"
SEED = 7
BURST_STEP = 3


def bursts(video: str, limit: int | None = None) -> list[tuple[int, list[np.ndarray]]]:
    """Clean 3-frame bursts cached by make_impact_dataset.py (held out from the reference window)."""
    import cv2

    d = CACHE / video
    idx = sorted(int(p.stem) for p in d.glob("*.png"))
    starts = [i for i in idx if i + BURST_STEP in idx and i + 2 * BURST_STEP in idx and (i - BURST_STEP) not in idx]
    out = []
    for s in starts[:limit]:
        out.append((s, [cv2.imread(str(d / f"{s + k * BURST_STEP}.png")) for k in range(3)]))
    return out


def reference(video: str) -> Any:
    from visiondoctor.health.reference import Reference

    return Reference.load(CACHE / video / "reference")


def videos() -> list[str]:
    return sorted(p.name for p in CACHE.iterdir() if (p / "reference.json").exists())


def bootstrap_ci(values: list[float] | np.ndarray, fn: Any = np.mean, n: int = 1000, seed: int = SEED) -> list[float]:
    v = np.asarray(values, float)
    if len(v) == 0:
        return [float("nan"), float("nan")]
    rng = np.random.default_rng(seed)
    stats = [fn(v[rng.integers(0, len(v), len(v))]) for _ in range(n)]
    return [round(float(np.percentile(stats, 2.5)), 4), round(float(np.percentile(stats, 97.5)), 4)]


def save(name: str, obj: Any) -> Path:
    p = RESULTS / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, indent=2, default=lambda o: o.tolist() if hasattr(o, "tolist") else str(o)))
    print("wrote", p)
    return p

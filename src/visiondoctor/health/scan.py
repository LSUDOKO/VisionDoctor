"""Run all checks on a burst of frames → HealthReport (docs/03 §3.12)."""

from __future__ import annotations

import time
from collections.abc import Callable

import numpy as np

from visiondoctor.health import heatmap
from visiondoctor.health.checks import (
    color_cast,
    drift,
    exposure,
    freeze,
    glare,
    haze,
    noise,
    occlusion,
    sharpness,
    smudge,
    vibration,
)
from visiondoctor.health.checks.base import CameraState, ScanContext
from visiondoctor.health.features import compute_features
from visiondoctor.health.reference import Reference
from visiondoctor.health.types import CRITICAL_CHECKS, CheckResult, HealthReport
from visiondoctor.observability.metrics import emit

# Cheap checks first; geometric (drift, vibration) last.
CHECKS: list[tuple[str, Callable[[ScanContext], CheckResult]]] = [
    ("freeze", freeze.check),
    ("exposure", exposure.check),
    ("glare", glare.check),
    ("color_cast", color_cast.check),
    ("noise", noise.check),
    ("haze", haze.check),
    ("sharpness", sharpness.check),
    ("occlusion", occlusion.check),
    ("smudge", smudge.check),
    ("drift", drift.check),
    ("vibration", vibration.check),
]


def overall(checks: dict[str, CheckResult]) -> float:
    scores = [c.score for c in checks.values()]
    crit = [checks[n].score for n in CRITICAL_CHECKS if n in checks]
    return float(min(min(crit, default=1.0), float(np.mean(scores))))


def scan(
    camera_id: str,
    frames: list[np.ndarray],
    reference: Reference,
    state: CameraState | None = None,
    now: float | None = None,
    only: set[str] | None = None,
) -> HealthReport:
    """Scan a burst (oldest→newest) of BGR frames from one camera against its reference."""
    t0 = time.perf_counter()
    state = state or CameraState()
    prepared = [reference.prepare(f) for f in frames]
    feats = [compute_features(p) for p in prepared]
    lum_med = float(np.median([f.glob["lum_median"] for f in feats]))
    bname, bucket = reference.bucket_for(lum_med)
    ctx = ScanContext(reference, bname, bucket, prepared, feats, state, now=now or time.time())
    t_feat = (time.perf_counter() - t0) * 1000
    results: dict[str, CheckResult] = {}
    op_ms: dict[str, float] = {"features": t_feat}
    for name, fn in CHECKS:
        if only and name not in only:
            continue
        t = time.perf_counter()
        results[name] = fn(ctx)
        op_ms[name] = (time.perf_counter() - t) * 1000
    q = heatmap.quality_map(ctx)
    scan_ms = (time.perf_counter() - t0) * 1000
    for name, ms in op_ms.items():
        emit("ScanLatencyMs", ms, "Milliseconds", check=name)
    return HealthReport(
        camera_id=camera_id,
        ts=ctx.now,
        checks=results,
        overall_score=overall(results),
        heatmap=q,
        scan_ms=scan_ms,
        reference_bucket=bname,
        op_ms=op_ms,
    )

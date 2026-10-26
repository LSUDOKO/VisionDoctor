"""Run all checks on a burst of frames → HealthReport (docs/03 §3.12)."""

from __future__ import annotations

import time
from collections.abc import Callable

import cv2
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
from visiondoctor.observability.metrics import emit, timer

# Order matters: later checks read earlier results to avoid double-counting one cause
# (e.g. smudge defers to sharpness/vibration, exposure defers to glare). Drift runs before the
# tile checks so they can be evaluated on drift-compensated frames.
CHECKS: list[tuple[str, Callable[[ScanContext], CheckResult]]] = [
    ("freeze", freeze.check),
    ("glare", glare.check),
    ("occlusion", occlusion.check),
    ("exposure", exposure.check),
    ("color_cast", color_cast.check),
    ("noise", noise.check),
    ("haze", haze.check),
    ("drift", drift.check),
    ("sharpness", sharpness.check),
    ("vibration", vibration.check),
    ("smudge", smudge.check),
]
GLOBAL_LOSS = {"freeze"}  # a dead/uniform frame explains every other symptom


def _drift_compensated(ctx: ScanContext, d: CheckResult) -> ScanContext:
    """Warp frames back into reference geometry so tile checks compare like with like."""
    H = d.evidence.get("H")
    if d.severity < 1 or d.abstained or H is None or d.evidence.get("inlier_ratio", 0) < 0.25:
        return ctx
    if abs(np.linalg.det(np.asarray(H))) < 1e-6:
        return ctx
    Hinv = np.linalg.inv(np.asarray(H))
    h, w = ctx.frames[0].shape[:2]
    with timer("warpPerspective"):
        frames = [
            cv2.warpPerspective(f, Hinv, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REFLECT101)
            for f in ctx.frames
        ]
    d.evidence["tile_checks_aligned"] = True
    new = ScanContext(
        ctx.reference, ctx.bucket_name, ctx.bucket, frames, [compute_features(f) for f in frames], ctx.state, ctx.now
    )
    new.results = ctx.results
    return new


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
        ctx.results[name] = results[name]
        op_ms[name] = (time.perf_counter() - t) * 1000
        if name == "drift":
            ctx = _drift_compensated(ctx, results[name])
    dead = results.get("freeze")
    if dead is not None and dead.evidence.get("dead"):
        for n, r in results.items():
            if n != "freeze" and r.severity:
                r.evidence["explained_by"] = "freeze"
                r.severity = 0
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

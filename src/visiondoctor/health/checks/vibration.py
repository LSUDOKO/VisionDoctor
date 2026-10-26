"""Vibration / shake: frame-to-frame LK optical flow + partial affine on static features.

docs/03 §3.3. Vibration = high std of inter-frame translation with ~zero mean (drift is a
constant offset and leaves consecutive frames aligned).
"""

from __future__ import annotations

import cv2
import numpy as np

from visiondoctor.health.checks.base import ScanContext
from visiondoctor.health.types import CheckResult, band
from visiondoctor.observability.metrics import timer

JITTER_PX_EDGES = (0.8, 1.5, 3.0, 6.0, 12.0)


def check(ctx: ScanContext) -> CheckResult:
    if len(ctx.feats) < 3:
        return CheckResult("vibration", 0, {"reason": "burst_too_short"}, abstained=True)
    mask = ctx.bucket.static_mask
    txs, tys, rots = [], [], []
    for a, b in zip(ctx.feats, ctx.feats[1:], strict=False):
        with timer("goodFeaturesToTrack"):
            p0 = cv2.goodFeaturesToTrack(a.gray, maxCorners=300, qualityLevel=0.01, minDistance=8, mask=mask)
        if p0 is None or len(p0) < 10:
            continue
        with timer("calcOpticalFlowPyrLK"):
            p1, st, _ = cv2.calcOpticalFlowPyrLK(a.gray, b.gray, p0, None, winSize=(21, 21), maxLevel=3)
        ok = st.ravel() == 1
        if ok.sum() < 8:
            continue
        M, _ = cv2.estimateAffinePartial2D(p0[ok], p1[ok], method=cv2.RANSAC, ransacReprojThreshold=2.0)
        if M is None:
            continue
        txs.append(float(M[0, 2]))
        tys.append(float(M[1, 2]))
        rots.append(float(np.degrees(np.arctan2(M[1, 0], M[0, 0]))))
    if len(txs) < 2:
        return CheckResult("vibration", 0, {"reason": "too_few_tracks"}, abstained=True)
    jitter = float(np.hypot(np.std(txs), np.std(tys)))
    mean_shift = float(np.hypot(np.mean(txs), np.mean(tys)))
    peak = float(np.max(np.hypot(txs, tys)))
    sev = band(max(jitter, 0.5 * peak), JITTER_PX_EDGES)
    return CheckResult(
        "vibration",
        sev,
        {"jitter_px": jitter, "peak_px": peak, "mean_shift_px": mean_shift, "rot_std_deg": float(np.std(rots))},
    )

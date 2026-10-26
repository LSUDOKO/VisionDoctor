"""Colour cast / stuck IR-cut filter: Lab a/b shift and grey-world deviation (docs/03 §3.9)."""

from __future__ import annotations

import math

from visiondoctor.health.checks.base import ScanContext
from visiondoctor.health.types import CheckResult, band

LAB_DIST_EDGES = (3.0, 5.0, 8.0, 12.0, 18.0)


def check(ctx: ScanContext) -> CheckResult:
    ra, rb = ctx.bucket.glob_mean["lab_a"], ctx.bucket.glob_mean["lab_b"]
    ca, cb = ctx.glob["lab_a"], ctx.glob["lab_b"]
    da, db = ca - ra, cb - rb
    # Haze desaturates and gain saturates: both scale the mean chroma vector (cur ≈ k·ref).
    # Only the part of the shift not explained by such scaling is a colour cast.
    ref_norm2 = ra * ra + rb * rb
    k = (ca * ra + cb * rb) / ref_norm2 if ref_norm2 > 9.0 else 1.0
    if 0.3 <= k <= 1.7 and ref_norm2 > 9.0:
        dist = math.hypot(ca - k * ra, cb - k * rb)
    else:
        dist = math.hypot(da, db)
    sev = band(dist, LAB_DIST_EDGES)
    hint = None
    if sev and da > 4 and db < 2 and ctx.bucket_name == "day":
        hint = "magenta cast in daylight: possible stuck IR-cut filter"
    return CheckResult(
        "color_cast",
        sev,
        {
            "delta_a": da,
            "delta_b": db,
            "lab_dist": dist,
            "chroma_scale": k,
            "grayworld_dev": ctx.glob["grayworld_dev"],
            "ref_grayworld_dev": ctx.bucket.glob_mean["grayworld_dev"],
            "hint": hint,
        },
    )

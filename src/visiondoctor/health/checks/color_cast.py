"""Colour cast / stuck IR-cut filter: Lab a/b shift and grey-world deviation (docs/03 §3.9)."""

from __future__ import annotations

import math

from visiondoctor.health.checks.base import ScanContext
from visiondoctor.health.types import CheckResult, band

LAB_DIST_EDGES = (3.0, 5.0, 8.0, 12.0, 18.0)


def check(ctx: ScanContext) -> CheckResult:
    da = ctx.glob["lab_a"] - ctx.bucket.glob_mean["lab_a"]
    db = ctx.glob["lab_b"] - ctx.bucket.glob_mean["lab_b"]
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
            "grayworld_dev": ctx.glob["grayworld_dev"],
            "ref_grayworld_dev": ctx.bucket.glob_mean["grayworld_dev"],
            "hint": hint,
        },
    )

"""Sensor noise: Immerkaer σ estimate vs reference (docs/03 §3.10)."""

from __future__ import annotations

from visiondoctor.health.checks.base import ScanContext
from visiondoctor.health.types import CheckResult, band

RATIO_EDGES = (1.5, 2.0, 2.7, 3.6, 5.0)


def check(ctx: ScanContext) -> CheckResult:
    ref = max(ctx.bucket.glob_mean["noise"], 0.3)
    ratio = ctx.glob["noise"] / ref
    return CheckResult("noise", band(ratio, RATIO_EDGES), {"sigma": ctx.glob["noise"], "ref_sigma": ref, "ratio": ratio})

"""Sensor noise (docs/03 §3.10).

Primary signal: temporal noise σ from the burst (robust MAD of consecutive-frame differences),
which ignores static fine texture that the single-frame Immerkaer estimator mistakes for noise.
The Immerkaer σ is kept as evidence and used when only one frame is available.
"""

from __future__ import annotations

from visiondoctor.health.checks.base import ScanContext
from visiondoctor.health.features import temporal_sigma
from visiondoctor.health.types import CheckResult, band

RATIO_EDGES = (1.5, 2.0, 2.7, 3.6, 5.0)


def check(ctx: ScanContext) -> CheckResult:
    ref_sp = max(ctx.bucket.glob_mean["noise"], 0.3)
    ratio_sp = ctx.glob["noise"] / ref_sp
    ev: dict[str, object] = {"sigma": ctx.glob["noise"], "ref_sigma": ref_sp, "spatial_ratio": ratio_sp}
    if len(ctx.feats) >= 2 and "noise_t" in ctx.bucket.glob_mean:
        st = temporal_sigma([f.gray for f in ctx.feats])
        ref_t = max(ctx.bucket.glob_mean["noise_t"], 0.5)
        ratio = st / ref_t
        ev |= {"temporal_sigma": st, "ref_temporal_sigma": ref_t, "ratio": ratio}
    else:
        ratio = ratio_sp
        ev["ratio"] = ratio
    return CheckResult("noise", band(ratio, RATIO_EDGES), ev)

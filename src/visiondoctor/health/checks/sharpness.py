"""Defocus: uniform loss of contrast-normalised sharpness across all textured tiles (docs/03 §3.1).

Laplacian variance and Tenengrad are divided by contrast², which makes them invariant to gain
(exposure) and haze (both affine in intensity), so only real blur moves them. Local loss is
left to the smudge check.
"""

from __future__ import annotations

import numpy as np

from visiondoctor.health.checks.base import ScanContext
from visiondoctor.health.types import CheckResult, band

LOSS_EDGES = (0.3, 0.45, 0.6, 0.72, 0.85)
UNIFORM_TILE_RATIO = 0.6
UNIFORM_MIN_FRAC = 0.7


def check(ctx: ScanContext) -> CheckResult:
    sharp_ratio = ctx.ratio("sharp_n")
    con = max(ctx.glob["contrast"], 1.0) ** 2
    ref_con = max(ctx.bucket.glob_mean["contrast"], 1.0) ** 2
    ten_ratio = (ctx.glob["tenengrad"] / con) / max(ctx.bucket.glob_mean["tenengrad"] / ref_con, 1e-9)
    hf = ctx.ratio("hf_ratio")
    tile_r = ctx.tile_ratio("sharp_n")
    tex = ctx.textured
    uniform_frac = float((tile_r[tex] < UNIFORM_TILE_RATIO).mean()) if tex.any() else 0.0
    loss = float(1.0 - min(1.0, np.sqrt(max(sharp_ratio, 0.0) * max(ten_ratio, 0.0))))
    sev = band(loss, LOSS_EDGES)
    if uniform_frac < UNIFORM_MIN_FRAC:
        sev = min(sev, 1)  # local loss → smudge, not defocus
    return CheckResult(
        "sharpness",
        sev,
        {
            "lap_var": ctx.glob["lap_var"],
            "lap_ratio": ctx.ratio("lap_var"),
            "sharp_n_ratio": sharp_ratio,
            "tenengrad_ratio": ten_ratio,
            "hf_ratio": hf,
            "uniform_frac": uniform_frac,
            "loss": loss,
        },
        region_mask=((tile_r < UNIFORM_TILE_RATIO) & tex).astype(np.uint8) if sev else None,
    )

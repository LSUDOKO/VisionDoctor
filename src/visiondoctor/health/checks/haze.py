"""Haze / fog / condensation: dark channel ↑, contrast ↓, saturation ↓ vs reference (docs/03 §3.4).

Exposure gain scales contrast with luminance; haze lowers contrast while luminance rises, so we
require contrast to fall relative to luminance. Tile map exposes non-uniform condensation.
"""

from __future__ import annotations

import numpy as np

from visiondoctor.health.checks.base import ScanContext
from visiondoctor.health.types import CheckResult, band

CONTRAST_LOSS_EDGES = (0.12, 0.22, 0.32, 0.45, 0.6)


def check(ctx: ScanContext) -> CheckResult:
    con_r = ctx.ratio("contrast")
    lum_r = ctx.ratio("lum")
    sat_r = ctx.ratio("sat")
    ref_dark = ctx.bucket.glob_mean["dark"]
    dark_up = (ctx.glob["dark"] - ref_dark) / max(ref_dark, 10.0)
    rel_con = con_r / max(lum_r, 1e-6)  # ≈1 under pure gain change
    loss = float(max(0.0, 1.0 - rel_con))
    sev = band(loss, CONTRAST_LOSS_EDGES)
    if dark_up < 0.05 or ctx.glob["clip_high"] - ctx.bucket.glob_mean["clip_high"] > 0.1:
        sev = 0  # no veil (or it's blown-out highlights) → not haze
    tile_con = ctx.tile_ratio("contrast")
    tile_dark = ctx.tiles["dark"] - ctx.bucket.tile_mean["dark"]
    hazy_tiles = (tile_con < 0.8) & (tile_dark > 5)
    return CheckResult(
        "haze",
        sev,
        {
            "dark_channel": ctx.glob["dark"],
            "dark_delta_rel": float(dark_up),
            "contrast_ratio": con_r,
            "lum_ratio": lum_r,
            "saturation_ratio": sat_r,
            "contrast_loss": loss,
            "hazy_tile_frac": float(hazy_tiles.mean()),
            "uniform": bool(hazy_tiles.mean() > 0.8),
        },
        region_mask=hazy_tiles.astype(np.uint8) if sev else None,
    )

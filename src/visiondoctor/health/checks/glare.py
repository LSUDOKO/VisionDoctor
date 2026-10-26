"""Glare / lens flare: saturated low-saturation blobs (V≥250, S≤40) beyond the reference (docs/03 §3.5)."""

from __future__ import annotations

import cv2
import numpy as np

from visiondoctor.health.checks.base import ScanContext
from visiondoctor.health.types import CheckResult, band
from visiondoctor.observability.metrics import timer

DELTA_FRAC_EDGES = (0.01, 0.025, 0.05, 0.1, 0.2)


def check(ctx: ScanContext) -> CheckResult:
    mask = ctx.feats[-1].extras["glare"]
    with timer("connectedComponentsWithStats"):
        n, _, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    largest = float(stats[1:, cv2.CC_STAT_AREA].max() / mask.size) if n > 1 else 0.0
    delta = ctx.glob["glare_frac"] - ctx.bucket.glob_mean["glare_frac"]
    sev = band(max(delta, 0.0), DELTA_FRAC_EDGES)
    # Global over-exposure also saturates pixels, but brightens every tile; glare is local, so the
    # dimmest 20% of tiles keep their reference luminance.
    p20 = ctx.lum_ratio_pct(20)
    explained = None
    if p20 > 1.12:
        explained, sev = "exposure", 0
    g = ctx.grid
    tiles = cv2.resize(mask, (g, g), interpolation=cv2.INTER_AREA) > 40
    return CheckResult(
        "glare",
        sev,
        {
            "glare_frac": ctx.glob["glare_frac"],
            "delta_frac": float(delta),
            "largest_blob_frac": largest,
            "blobs": n - 1,
            "tile_lum_ratio_p20": p20,
            "explained_by": explained,
        },
        region_mask=tiles.astype(np.uint8) if sev else None,
    )

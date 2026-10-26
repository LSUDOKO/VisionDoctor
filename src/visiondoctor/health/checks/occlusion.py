"""Occlusion / covered lens / foreign object (docs/03 §3.7).

A tile is occluded when it has become near-uniform AND either lost its edges (textured tiles)
or changed brightness (flat tiles). MOG2 foreground that persists across scans marks a static
foreign object. Occluded tiles → findContours → bounding boxes for evidence/VLM crops.
"""

from __future__ import annotations

import cv2
import numpy as np

from visiondoctor.health.checks.base import ScanContext
from visiondoctor.health.types import CheckResult, band
from visiondoctor.observability.metrics import timer

FRAC_EDGES = (0.04, 0.08, 0.15, 0.3, 0.6)
UNIFORM_CONTRAST = 6.0
UNIFORM_ENTROPY = 2.0


def check(ctx: ScanContext) -> CheckResult:
    edge_r = ctx.tile_ratio("edge")
    uniform = (ctx.tiles["contrast"] < UNIFORM_CONTRAST) | (ctx.tiles["entropy"] < UNIFORM_ENTROPY)
    lum_shift = np.abs(ctx.tiles["lum"] - ctx.bucket.tile_mean["lum"]) > 25
    tex = ctx.textured
    occluded = uniform & np.where(tex, edge_r < 0.2, lum_shift)

    # Static foreground: MOG2 on each frame; tiles foreground in every scan for 3+ scans.
    g = ctx.grid
    fg_tiles = np.ones((g, g), bool)
    for f in ctx.frames:
        with timer("mog2_apply"):
            fg = ctx.state.mog2.apply(f, learningRate=0.002)
        fg_tiles &= cv2.resize(fg, (g, g), interpolation=cv2.INTER_AREA) > 160
    st = ctx.state
    st.static_fg = fg_tiles.astype(np.uint8) if st.static_fg is None else (st.static_fg & fg_tiles).astype(np.uint8)
    st.static_fg_scans = st.static_fg_scans + 1 if st.static_fg.any() else 0
    static_obj = st.static_fg.astype(bool) if st.static_fg_scans >= 3 else np.zeros((g, g), bool)
    occluded |= static_obj & (edge_r < 0.5)

    frac = float(occluded.mean())
    sev = band(frac, FRAC_EDGES)
    ev = {
        "occluded_frac": frac,
        "occluded_tiles": int(occluded.sum()),
        "static_object_tiles": int(static_obj.sum()),
        "bboxes": ctx.tiles_to_bboxes(occluded) if occluded.any() else [],
    }
    return CheckResult("occlusion", sev, ev, region_mask=occluded.astype(np.uint8) if sev else None)

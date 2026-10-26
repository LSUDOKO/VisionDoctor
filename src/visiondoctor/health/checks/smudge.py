"""Smudge / dirty lens / spider web: local, persistent partial loss of sharpness (docs/03 §3.8).

Edges are reduced (not removed, unlike occlusion) in a minority of tiles, and the loss must be
present in ≥60% of burst frames (different scene content) to count. Thin bright high-frequency
structures in dark scenes are flagged as a possible spider web for the VLM.
"""

from __future__ import annotations

import math

import numpy as np

from visiondoctor.health.checks.base import ScanContext
from visiondoctor.health.types import CheckResult, band

FRAC_EDGES = (0.03, 0.06, 0.12, 0.25, 0.45)
LOW, HIGH = 0.02, 0.6
DEFOCUS_FRAC = 0.75


def check(ctx: ScanContext) -> CheckResult:
    tex = ctx.textured
    if not tex.any():
        return CheckResult("smudge", 0, {"reason": "no_texture"}, abstained=True)
    votes = np.zeros(tex.shape, int)
    for f in ctx.feats:
        r = ctx.tile_ratio("sharp_n", f.tiles["sharp_n"])
        z = ctx.tile_z_drop("sharp_n", f.tiles["sharp_n"])
        not_flat = f.tiles["contrast"] >= 6.0
        votes += ((r > LOW) & (r < HIGH) & (z > 3.0) & not_flat & tex).astype(int)
    need = math.ceil(0.6 * len(ctx.feats))
    smudged = votes >= need
    frac = float(smudged.sum() / tex.sum())
    sev = band(frac, FRAC_EDGES)
    ev: dict[str, object] = {"smudged_frac": frac, "smudged_tiles": int(smudged.sum()), "frames_needed": need}
    if frac > DEFOCUS_FRAC:
        ev["explained_by"] = "sharpness"
        sev = 0
    # Spider-web hint: dark scene but local high-frequency energy went UP near the lens.
    if ctx.glob["lum"] < 60:
        hf_up = (ctx.tile_ratio("lap_var") > 2.5) & (ctx.tiles["lum"] > ctx.bucket.tile_mean["lum"] + 10)
        ev["spider_web_hint"] = bool(hf_up.sum() >= 2)
    if smudged.any():
        ev["bboxes"] = ctx.tiles_to_bboxes(smudged)
    return CheckResult("smudge", sev, ev, region_mask=smudged.astype(np.uint8) if sev else None)

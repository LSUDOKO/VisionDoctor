"""Smudge / dirty lens / spider web: local, persistent partial loss of sharpness (docs/03 §3.8).

Edges are reduced (not removed, unlike occlusion) in a minority of tiles, and the loss must be
present in ≥60% of burst frames AND in each of the last ``PERSIST_SCANS`` scans (different scene
content each time) to count — a crowd passing over pavement does not stay in the same tiles. Thin bright high-frequency
structures in dark scenes are flagged as a possible spider web for the VLM.
"""

from __future__ import annotations

import math

import numpy as np

from visiondoctor.health.checks.base import ScanContext
from visiondoctor.health.types import CheckResult, band

FRAC_EDGES = (0.04, 0.07, 0.12, 0.2, 0.35)
LOW, HIGH = 0.02, 0.6
DEFOCUS_FRAC = 0.75
PERSIST_SCANS = 3


def check(ctx: ScanContext) -> CheckResult:
    tex = ctx.textured & ctx.static_tiles  # moving crowds would mimic local blur
    if not tex.any():
        return CheckResult("smudge", 0, {"reason": "no_texture"}, abstained=True)
    for other in ("sharpness", "vibration", "exposure", "glare", "occlusion", "freeze", "noise"):
        if ctx.sev(other) >= 2:
            return CheckResult("smudge", 0, {"explained_by": other})
    if ctx.sev("drift") >= 2:
        # Tiles were re-warped into reference geometry; interpolation softens them. Re-check
        # after the realign repair instead of guessing now.
        return CheckResult("smudge", 0, {"reason": "deferred_until_realigned"}, abstained=True)
    votes = np.zeros(tex.shape, int)
    web_votes = np.zeros(tex.shape, int)
    for f in ctx.feats:
        r = ctx.tile_ratio("sharp_n", f.tiles["sharp_n"])
        z = ctx.tile_z_drop("sharp_n", f.tiles["sharp_n"])
        not_flat = f.tiles["contrast"] >= 6.0
        votes += ((r > LOW) & (r < HIGH) & (z > 3.0) & not_flat & tex).astype(int)
        # Foreign thin structure on the lens (spider web, lit by IR at night): new bright
        # high-frequency energy. Daytime crowds also add edges, so only judged in the dark.
        if ctx.glob["lum"] < 70:
            lap_r = ctx.tile_ratio("lap_var", f.tiles["lap_var"])
            web_votes += ((lap_r > 3.0) & (ctx.tile_z_drop("lap_var", f.tiles["lap_var"]) < -6.0)).astype(int)
    need = math.ceil(0.6 * len(ctx.feats))
    web = web_votes >= len(ctx.feats)  # must be present in every frame
    now_smudged = (votes >= need) | web
    hist = ctx.state.smudge_hist
    hist.append(now_smudged)
    del hist[:-PERSIST_SCANS]
    smudged = np.logical_and.reduce(hist) if len(hist) == PERSIST_SCANS else np.zeros_like(now_smudged)
    frac = float(smudged.sum() / tex.sum())
    sev = band(frac, FRAC_EDGES)
    ev: dict[str, object] = {
        "smudged_frac": frac,
        "smudged_tiles": int(smudged.sum()),
        "web_tiles": int(web.sum()),
        "candidate_tiles": int(now_smudged.sum()),
        "persist_scans": len(hist),
        "frames_needed": need,
    }
    if frac > DEFOCUS_FRAC:
        ev["explained_by"] = "sharpness"
        sev = 0
    # Spider-web hint: dark scene but local high-frequency energy went UP near the lens.
    if ctx.glob["lum"] < 60:
        hf_up = (ctx.tile_ratio("lap_var") > 2.5) & (ctx.tiles["lum"] > ctx.bucket.tile_mean["lum"] + 10)
        ev["spider_web_hint"] = bool(hf_up.sum() >= 2)
    if web.sum() >= 2:
        ev["spider_web_hint"] = True
    if smudged.any():
        ev["bboxes"] = ctx.tiles_to_bboxes(smudged)
    return CheckResult("smudge", sev, ev, region_mask=smudged.astype(np.uint8) if sev else None)

"""Occlusion / covered lens / foreign object (docs/03 §3.7).

Pixel-level test against the reference background: a pixel is occluded when its local
contrast collapsed (box-filter std < 3 and < 15% of the reference's) — haze and gain scale
contrast but never remove it — or when a textureless area changed brightness strongly.
MOG2 foreground that persists across scans marks a static foreign object. The occluded mask
→ findContours (TRUCO) → bounding boxes for evidence crops and the VLM.
"""

from __future__ import annotations

import cv2
import numpy as np

from visiondoctor.health.checks.base import ScanContext
from visiondoctor.health.types import CheckResult, band
from visiondoctor.observability.metrics import timer

FRAC_EDGES = (0.04, 0.08, 0.15, 0.3, 0.6)
WIN = (15, 15)
STATIC_OBJECT_S = 300.0


def local_std(gray: np.ndarray) -> np.ndarray:
    g = gray.astype(np.float32)
    with timer("boxFilter"):
        m = cv2.boxFilter(g, -1, WIN)
        m2 = cv2.boxFilter(g * g, -1, WIN)
    return np.sqrt(np.maximum(m2 - m * m, 0.0))


def check(ctx: ScanContext) -> CheckResult:
    cur = np.median(np.stack(ctx.frames), axis=0).astype(np.uint8) if len(ctx.frames) > 2 else ctx.frames[-1]
    cur_g = cv2.cvtColor(cur, cv2.COLOR_BGR2GRAY)
    ref_g = cv2.cvtColor(ctx.bucket.background, cv2.COLOR_BGR2GRAY)
    s_cur, s_ref = local_std(cur_g), local_std(ref_g)
    flat_now = (s_cur < 3.0) & (s_cur < 0.15 * np.maximum(s_ref, 1e-3))
    lost_texture = flat_now & (s_ref > 6.0)
    # Haze and gain are global affine maps cur ≈ a·ref + b; only residuals beyond that are occluders.
    sub_c, sub_r = cur_g[::4, ::4].ravel().astype(np.float64), ref_g[::4, ::4].ravel().astype(np.float64)
    a, b = np.polyfit(sub_r, sub_c, 1)
    resid = np.abs(cur_g.astype(np.float32) - (a * ref_g.astype(np.float32) + b))
    lum_jump = (resid > 30) & (s_cur < 3.0) & (s_ref <= 6.0)
    bright = cv2.dilate(ctx.feats[-1].extras["glare"], np.ones((15, 15), np.uint8)) > 0
    occ = (lost_texture | lum_jump) & ~bright & (cur_g < 240)
    lum_r = ctx.ratio("lum")
    if lum_r > 1.3:
        occ &= cur_g < 235  # blown highlights → exposure check
    if lum_r < 0.6:
        occ &= cur_g > 15  # crushed shadows → exposure check
    occ_u8 = cv2.morphologyEx(occ.astype(np.uint8) * 255, cv2.MORPH_OPEN, np.ones((9, 9), np.uint8))

    # Static foreground: MOG2 on each frame; tiles that stay foreground in every scan for
    # ≥ STATIC_OBJECT_S seconds (and ≥ 5 scans) are a foreign object, not a loitering person.
    g = ctx.grid
    fg_tiles = np.ones((g, g), bool)
    for f in ctx.frames:
        with timer("mog2_apply"):
            fg = ctx.state.mog2.apply(f, learningRate=0.002)
        fg_tiles &= cv2.resize(fg, (g, g), interpolation=cv2.INTER_AREA) > 160
    st = ctx.state
    st.static_fg = fg_tiles.astype(np.uint8) if st.static_fg is None else (st.static_fg & fg_tiles).astype(np.uint8)
    if st.static_fg.any():
        st.static_fg_scans += 1
        st.static_fg_since = st.static_fg_since or ctx.now
    else:
        st.static_fg, st.static_fg_scans, st.static_fg_since = None, 0, None
    long_enough = st.static_fg_since is not None and ctx.now - st.static_fg_since >= STATIC_OBJECT_S
    static_obj = (
        st.static_fg.astype(bool) if (st.static_fg is not None and long_enough and st.static_fg_scans >= 5)
        else np.zeros((g, g), bool)
    )

    frac = float(occ_u8.mean() / 255.0)
    tiles = cv2.resize(occ_u8, (g, g), interpolation=cv2.INTER_AREA) > 127
    tiles |= static_obj
    frac = max(frac, float(static_obj.mean()))
    sev = band(frac, FRAC_EDGES)
    with timer("findContours"):
        contours, _ = cv2.findContours(occ_u8, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    boxes = sorted((list(cv2.boundingRect(c)) for c in contours), key=lambda b: -b[2] * b[3])[:5]
    ev = {
        "occluded_frac": frac,
        "occluded_tiles": int(tiles.sum()),
        "static_object_tiles": int(static_obj.sum()),
        "bboxes": boxes,
        "affine_gain": float(a),
        "affine_offset": float(b),
    }
    return CheckResult("occlusion", sev, ev, region_mask=tiles.astype(np.uint8) if sev else None)

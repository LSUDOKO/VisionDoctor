"""Under/over-exposure: luminance shift and clipping vs the same-luminance-bucket reference (docs/03 §3.6)."""

from __future__ import annotations

from visiondoctor.health.checks.base import ScanContext
from visiondoctor.health.types import CheckResult, band

LUM_REL_EDGES = (0.15, 0.25, 0.35, 0.5, 0.65)
CLIP_EDGES = (0.06, 0.12, 0.22, 0.35, 0.5)


def check(ctx: ScanContext) -> CheckResult:
    ref_lum = max(ctx.bucket.glob_mean["lum"], 5.0)
    dl = ctx.glob["lum"] - ref_lum
    rel = abs(dl) / ref_lum
    d_low = ctx.glob["clip_low"] - ctx.bucket.glob_mean["clip_low"]
    d_high = ctx.glob["clip_high"] - ctx.bucket.glob_mean["clip_high"]
    sev = max(band(rel, LUM_REL_EDGES), band(max(d_low, d_high, 0.0), CLIP_EDGES))
    rel_con = ctx.ratio("contrast") / max(ctx.ratio("lum"), 1e-6)
    explained = None
    if dl > 0 and rel_con < 0.75 and d_high < 0.1:
        explained, sev = "haze", 0  # brighter but flatter = veil, not gain
    if ctx.sev("occlusion") >= 3:
        explained, sev = "occlusion", min(sev, 1)
    if ctx.sev("glare") >= 2 and ctx.lum_ratio_pct(20) <= 1.12:
        explained, sev = "glare", min(sev, 1)
    direction = "over" if dl > 0 else "under"
    ev = {
        "mean_lum": ctx.glob["lum"],
        "ref_lum": ref_lum,
        "lum_delta_rel": dl / ref_lum,
        "clip_low": ctx.glob["clip_low"],
        "clip_high": ctx.glob["clip_high"],
        "direction": direction,
        "reference_bucket": ctx.bucket_name,
    }
    if explained:
        ev["explained_by"] = explained
    return CheckResult("exposure", sev, ev)

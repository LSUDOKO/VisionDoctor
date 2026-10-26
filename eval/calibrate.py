"""Threshold calibration on clean footage (docs/03 §9).

Scans every cached clean burst and records each check's continuous metric. Reports the 99.5th
percentile next to the frozen first severity-band edge, so REPORT.md can show the alarm
threshold sits above clean variation. Output: results/calibration/thresholds.json.
"""

from __future__ import annotations

import numpy as np

from common import bursts, reference, save, videos

from visiondoctor.health.checks import (
    color_cast, drift, exposure, glare, haze, noise, occlusion, sharpness, smudge, vibration,
)
from visiondoctor.health.checks.base import CameraState
from visiondoctor.health.scan import scan

METRIC = {  # check → (evidence key, first severity edge used by the check)
    "sharpness": ("loss", sharpness.LOSS_EDGES[0]),
    "drift": ("disp_pct_diag", drift.DISP_PCT_EDGES[0]),
    "vibration": ("jitter_px", vibration.JITTER_PX_EDGES[0]),
    "haze": ("contrast_loss", haze.CONTRAST_LOSS_EDGES[0]),
    "glare": ("delta_frac", glare.DELTA_FRAC_EDGES[0]),
    "exposure": ("lum_delta_rel", exposure.LUM_REL_EDGES[0]),
    "occlusion": ("occluded_frac", occlusion.FRAC_EDGES[0]),
    "smudge": ("candidate_tiles", None),
    "color_cast": ("lab_dist", color_cast.LAB_DIST_EDGES[0]),
    "noise": ("ratio", noise.RATIO_EDGES[0]),
}


def main() -> None:
    vals: dict[str, list[float]] = {k: [] for k in METRIC}
    n = 0
    for v in videos():
        ref = reference(v)
        st = CameraState()
        for _, clean in bursts(v):
            rep = scan(v, clean, ref, st)
            n += 1
            for chk, (key, _) in METRIC.items():
                x = rep.checks[chk].evidence.get(key)
                if isinstance(x, int | float):
                    vals[chk].append(abs(float(x)))
    out = {"clean_bursts": n, "videos": videos(), "checks": {}}
    for chk, (key, edge) in METRIC.items():
        a = np.array(vals[chk]) if vals[chk] else np.array([0.0])
        p995 = float(np.percentile(a, 99.5))
        out["checks"][chk] = {"metric": key, "p50": round(float(np.median(a)), 4), "p99_5": round(p995, 4),
                              "first_band_edge": edge, "margin_ok": None if edge is None else bool(p995 < edge)}
        if chk == "smudge":
            out["checks"][chk]["note"] = "severity also needs 3-scan persistence; candidate tile count shown"
    save("calibration/thresholds.json", out)


if __name__ == "__main__":
    main()

"""E4 — repair effectiveness for software-fixable faults at severities 1–5.

For each MOT17 burst: inject → scan → plan + verify repair. Records verified-success rate,
residual drift after realign, and accuracy recovered on REAL labels:
(AP_after − AP_degraded) / (AP_clean − AP_degraded).
"""

from __future__ import annotations

import numpy as np

from common import bootstrap_ci, bursts, reference, save, videos

from visiondoctor import repair
from visiondoctor.health.checks.base import CameraState
from visiondoctor.health.scan import scan
from visiondoctor.impact.agreement import average_precision
from visiondoctor.impact.detector import get_detector
from visiondoctor.repair.verify import verify
from visiondoctor.sim import sources
from visiondoctor.sim.faults import Fault

FIXABLE = ["drift", "exposure", "haze", "color_cast", "noise"]
STEP = 3


def ap(det, frames, gt):  # noqa: ANN001, ANN201
    ds = [det.detect(f) for f in frames]
    return average_precision([(d.boxes[d.classes == 0], d.scores[d.classes == 0]) for d in ds], gt)


def main() -> None:
    det = get_detector()
    rows = []
    for v in [x for x in videos() if x.startswith("MOT17")]:
        ref = reference(v)
        gt_all = sources.mot17_gt(v) or {}
        for start, clean in bursts(v, 3):
            gt = [gt_all.get(start + k * STEP, np.zeros((0, 4))) for k in range(3)]
            ap_clean = ap(det, clean, gt)
            for fault in FIXABLE:
                for sev in range(1, 6):
                    flt = Fault(fault, sev, seed=start)
                    frames = [flt.apply(f) for f in clean]
                    before = scan(v, frames, ref, CameraState())
                    row = {"video": v, "start": start, "fault": fault, "severity": sev,
                           "detected": before.checks[fault].severity >= 2, "ap_clean": ap_clean}
                    step = repair.plan(fault, before, ref) if row["detected"] else None
                    if step is None:
                        rows.append(row | {"attempted": False})
                        continue
                    step = repair.finalize(step, frames[-1])
                    ok, why = repair.check_bounds(step.type, step.params)
                    if not ok:
                        rows.append(row | {"attempted": False, "blocked": why})
                        continue
                    res = verify(v, step.type, repair.CorrectionProfile([step]), frames, ref, before)
                    fixed = [step.apply(f) for f in frames]
                    ap_deg, ap_fix = ap(det, frames, gt), ap(det, fixed, gt)
                    rec = (ap_fix - ap_deg) / (ap_clean - ap_deg) if ap_clean - ap_deg > 0.02 else None
                    row |= {"attempted": True, "verified": res.recovered, "ap_degraded": ap_deg, "ap_repaired": ap_fix,
                            "accuracy_recovered": rec, "severity_after": res.severity_after}
                    if fault == "drift":
                        row["residual_rot_deg"] = abs(float(res.report_after.checks["drift"].evidence.get("rot_deg", 0)))
                    rows.append(row)
            print(v, start, len(rows), flush=True)
    summary: dict[str, object] = {}
    for fault in FIXABLE:
        fr = [r for r in rows if r["fault"] == fault]
        att = [r for r in fr if r.get("attempted")]
        recs = [r["accuracy_recovered"] for r in att if r.get("accuracy_recovered") is not None]
        summary[fault] = {
            "n": len(fr), "detected_rate": round(np.mean([r["detected"] for r in fr]), 3),
            "verified_rate_of_attempted": round(float(np.mean([r["verified"] for r in att])), 3) if att else None,
            "accuracy_recovered_mean": round(float(np.mean(recs)), 3) if recs else None,
            "accuracy_recovered_ci95": bootstrap_ci(recs) if recs else None,
            "ap_clean_mean": round(float(np.mean([r["ap_clean"] for r in fr])), 3),
            "ap_degraded_mean": round(float(np.mean([r["ap_degraded"] for r in att])), 3) if att else None,
            "ap_repaired_mean": round(float(np.mean([r["ap_repaired"] for r in att])), 3) if att else None,
            "per_severity_verified": {s: round(float(np.mean([r["verified"] for r in att if r["severity"] == s])), 3)
                                      for s in range(1, 6) if any(r["severity"] == s for r in att)},
        }
        if fault == "drift":
            res_deg = [r["residual_rot_deg"] for r in att if "residual_rot_deg" in r]
            summary[fault]["residual_rot_deg_max"] = round(max(res_deg), 3) if res_deg else None  # type: ignore[index]
    save("e4/repair.json", summary)
    save("e4/rows.json", rows)


if __name__ == "__main__":
    main()

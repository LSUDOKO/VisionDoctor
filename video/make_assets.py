"""Generate the video's real proof images with VisionDoctor's own code + chart data from results/final.
Run with the project venv: ../.venv/bin/python make_assets.py"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import cv2
import numpy as np

from visiondoctor.health import heatmap
from visiondoctor.health.checks.base import CameraState
from visiondoctor.health.reference import learn_reference
from visiondoctor.health.scan import scan
from visiondoctor.impact.agreement import agreement, iou_matrix
from visiondoctor.impact.detector import get_detector
from visiondoctor.privacy.face_blur import blur_faces
from visiondoctor.repair import realign
from visiondoctor.sim import sources
from visiondoctor.sim.faults import Fault

HERE = Path(__file__).parent
A = HERE / "assets"
ROOT = HERE.parent
R = ROOT / "results" / "final"
A.mkdir(exist_ok=True)
INK = (245, 250, 252)  # cream in BGR
YEL = (92, 233, 255)
RED = (33, 85, 203)


def save(name: str, img: np.ndarray, q: int = 90) -> None:
    cv2.imwrite(str(A / name), img, [cv2.IMWRITE_JPEG_QUALITY, q])


def main() -> None:
    idx = list(range(0, 240, 4)) + [300, 303, 306, 309, 312]
    fr = sources.read_frames("MOT17-04", idx)
    ref = learn_reference("cam", [fr[i] for i in range(0, 240, 4)])
    burst = [fr[i] for i in (300, 303, 306, 309, 312)]
    clean = burst[-1]
    save("ref.jpg", ref.buckets["day"].background)
    save("clean.jpg", clean)

    # drift: 5 degrees (severity 4), measured by ORB + USAC MAGSAC
    d = Fault("drift", 4, seed=1)
    dburst = [d.apply(f) for f in burst]
    rep = scan("cam", dburst, ref, CameraState())
    ev = rep.checks["drift"].evidence
    save("drift.jpg", dburst[-1])
    fixed = realign.apply(dburst[-1], ev["H"])
    save("fixed.jpg", fixed)
    # match visualisation
    orb = cv2.ORB_create(1500)
    g1 = cv2.cvtColor(ref.buckets["day"].background, cv2.COLOR_BGR2GRAY)
    g2 = cv2.cvtColor(dburst[-1], cv2.COLOR_BGR2GRAY)
    k1, d1 = orb.detectAndCompute(g1, None)
    k2, d2 = orb.detectAndCompute(g2, None)
    knn = cv2.BFMatcher(cv2.NORM_HAMMING).knnMatch(d1, d2, k=2)
    good = sorted([p[0] for p in knn if len(p) == 2 and p[0].distance < 0.7 * p[1].distance], key=lambda m: m.distance)[:45]
    vis = cv2.drawMatches(ref.buckets["day"].background, k1, dburst[-1], k2, good, None, matchColor=YEL,
                          singlePointColor=None, flags=cv2.DrawMatchesFlags_NOT_DRAW_SINGLE_POINTS)
    save("matches.jpg", vis)

    # fault grid: real faults through the real scanner
    tiles = []
    meta = []
    for name, sev, check in [("haze", 3, "haze"), ("glare", 4, "glare"), ("smudge", 4, "smudge"),
                             ("occlusion", 4, "occlusion"), ("noise", 3, "noise"), ("color_cast", 4, "color_cast"),
                             ("defocus", 3, "sharpness"), ("exposure", 3, "exposure"), ("freeze", 5, "freeze")]:
        flt = Fault(name, sev, seed=7)
        fb = [flt.apply(f) for f in burst]
        st = CameraState()
        for _ in range(3 if name == "smudge" else 1):
            r = scan("cam", fb, ref, st)
        img = ref.prepare(fb[-1])
        img = cv2.resize(img, (480, 270))
        tiles.append(img)
        meta.append({"fault": name, "check": check, "severity": r.checks[check].severity})
        save(f"fault_{name}.jpg", img)
    json.dump(meta, open(A / "faults.json", "w"), indent=1)

    # twins: clean vs hazy detections and agreement (the label-free target)
    det = get_detector()
    hz = Fault("haze", 5, seed=2).apply(clean)
    dc, dh = det.detect(clean), det.detect(hz)
    ag = agreement(dh, dc)
    def boxes(img: np.ndarray, d, other) -> np.ndarray:  # noqa: ANN001
        out = img.copy()
        ok = (iou_matrix(d.boxes, other.boxes).max(axis=1) >= 0.5) if len(d) and len(other) else np.zeros(len(d), bool)
        for b, s, m in zip(d.boxes, d.scores, ok, strict=False):
            if s < 0.4:
                continue
            cv2.rectangle(out, (int(b[0]), int(b[1])), (int(b[2]), int(b[3])), YEL if m else RED, 2)
        return out
    save("twin_clean.jpg", boxes(clean, dc.filter(0.4), dh.filter(0.4)))
    save("twin_haze.jpg", boxes(hz, dh.filter(0.4), dc.filter(0.4)))
    json.dump({"agreement": round(ag, 2), "clean_dets": int(len(dc.filter(0.4))), "haze_dets": int(len(dh.filter(0.4)))},
              open(A / "twins.json", "w"))

    # hook: fog makes the detector go blind
    fog = Fault("haze", 5, seed=3).apply(fr[312])
    save("hook_fog.jpg", boxes(fog, det.detect(fog).filter(0.4), det.detect(fog).filter(0.4)))
    save("hook_clear.jpg", boxes(clean, dc.filter(0.4), dc.filter(0.4)))

    # privacy: real face mosaic
    face = cv2.imread(str(ROOT / "models" / "face_sample.jpg"))
    if face is not None:
        h, w = face.shape[:2]
        crop = face[: h // 2, w // 4: 3 * w // 4]
        save("face_before.jpg", cv2.resize(crop, (480, 270)))
        save("face_after.jpg", cv2.resize(blur_faces(crop)[0], (480, 270)))

    # crowd (failure case)
    c2 = sources.read_frames("MOT17-02", [400])[400]
    save("crowd.jpg", c2)

    # screenshots
    for f in ["live_aws_dashboard.png", "dashboard_trace_detail.png", "dashboard_incidents.png", "architecture.png"]:
        p = ROOT / "docs" / "img" / f
        if p.exists():
            shutil.copy(p, A / f)

    # chart data from measured results
    e1 = json.load(open(R / "e1_detection.json"))
    e3 = json.load(open(ROOT / "results" / "e3" / "scatter.json"))
    e4 = json.load(open(R / "e4_repair.json"))
    e5 = json.load(open(R / "e5_agent_policy.json"))
    bench = json.load(open(R / "bench_summary.json"))
    data = {
        "e1": {"ours": e1["recall_sev3plus"], "baseline": e1["baseline_recall_sev3plus"],
               "per_fault": {k: v["per_severity"]["3"]["recall"] for k, v in e1["faults"].items()}},
        "e3": {"pred": e3["ap"]["pred_drop"], "true": e3["ap"]["true_drop"],
               "rho": json.load(open(R / "e3_impact.json"))["true_ap_drop_mot17"]["spearman"]},
        "e4": {"clean": e4["drift"]["ap_clean_mean"], "degraded": e4["drift"]["ap_degraded_mean"],
               "repaired": e4["drift"]["ap_repaired_mean"], "recovered": e4["drift"]["accuracy_recovered_mean"]},
        "e5": {"correct": e5["correct_outcome_rate"], "alerts_agent": e5["agent_operator_alerts"],
               "alerts_baseline": e5["alarm_only_baseline_alerts"], "reduction": e5["operator_workload_reduction"]},
        "bench": {k: {"spm": v["scans_per_min"], "usd": v["usd_per_1M_scans"], "type": v["instance_type"]}
                  for k, v in bench["configs"].items()},
        "drift": {"rot": round(abs(ev["rot_deg"]), 2), "inliers": ev["inliers"], "disp_pct": round(ev["disp_pct_diag"], 2)},
    }
    json.dump(data, open(A / "data.json", "w"), indent=1)
    print(json.dumps({k: v for k, v in data.items() if k != "e3"}, indent=1))


if __name__ == "__main__":
    main()

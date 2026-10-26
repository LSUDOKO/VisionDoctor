"""E1 — fault detection per fault × severity (docs/06 §3), vs. a classic tamper-detector baseline.

Positive = the fault's expected check reaches severity ≥ 2 (the incident threshold). The
baseline uses global absolute thresholds with no per-camera reference and no hysteresis
(after Saglam 2009 / Huang 2014): dark/bright frame, low entropy, low Laplacian variance,
no frame change.
"""

from __future__ import annotations

import cv2
import numpy as np

from common import bootstrap_ci, bursts, reference, save, videos

from visiondoctor.health.checks.base import CameraState
from visiondoctor.health.scan import scan
from visiondoctor.sim.faults import EXPECTED_CHECK, FAULTS, Fault

ALTERNATIVES = {"smudge": ("smudge", "occlusion"), "spider_web": ("smudge",), "occlusion": ("occlusion", "freeze"),
                "dead": ("freeze",), "condensation": ("haze",)}


def baseline_alarm(frames: list[np.ndarray]) -> bool:
    g = [cv2.cvtColor(f, cv2.COLOR_BGR2GRAY) for f in frames]
    x = g[-1]
    hist = cv2.calcHist([x], [0], None, [64], [0, 256]).ravel()
    p = hist / hist.sum()
    p = p[p > 0]
    entropy = float(-(p * np.log2(p)).sum())
    lap = float(cv2.Laplacian(x, cv2.CV_64F).var())
    moved = max(float(cv2.absdiff(a, b).mean()) for a, b in zip(g, g[1:], strict=False))
    return bool(x.mean() < 30 or x.mean() > 225 or entropy < 3.0 or lap < 30 or moved < 0.5)


def main() -> None:
    rows = []
    for v in videos():
        ref = reference(v)
        for start, clean in bursts(v, 4):
            rep = scan(v, clean, ref, CameraState())
            rows.append({"video": v, "start": start, "fault": "none", "severity": 0,
                         "fired": [k for k, c in rep.checks.items() if c.severity >= 2], "baseline": baseline_alarm(clean)})
            for name in FAULTS:
                for sev in range(1, 6):
                    flt = Fault(name, sev, seed=start)
                    frames = [flt.apply(f) for f in clean]
                    st = CameraState()
                    for _ in range(3 if name in ("smudge", "spider_web") else 1):
                        rep = scan(v, frames, ref, st)
                    rows.append({"video": v, "start": start, "fault": name, "severity": sev,
                                 "fired": [k for k, c in rep.checks.items() if c.severity >= 2],
                                 "baseline": baseline_alarm(frames)})
        print(v, len(rows), flush=True)
    table: dict[str, dict[str, object]] = {}
    for name in FAULTS:
        exp = ALTERNATIVES.get(name, (EXPECTED_CHECK[name],))
        per_sev = {}
        for sev in range(1, 6):
            hits = [any(e in r["fired"] for e in exp) for r in rows if r["fault"] == name and r["severity"] == sev]
            base = [r["baseline"] for r in rows if r["fault"] == name and r["severity"] == sev]
            per_sev[sev] = {"recall": round(float(np.mean(hits)), 3), "ci95": bootstrap_ci(hits),
                            "baseline_recall": round(float(np.mean(base)), 3), "n": len(hits)}
        # precision of the expected check: how often it fires when this fault is NOT present
        others = [r for r in rows if r["fault"] != name]
        fp = sum(any(e in r["fired"] for e in exp) and EXPECTED_CHECK.get(r["fault"], "") not in exp for r in others)
        tp = sum(any(e in r["fired"] for e in exp) for r in rows if r["fault"] == name and r["severity"] >= 3)
        table[name] = {"per_severity": per_sev, "precision_sev3plus": round(tp / max(tp + fp, 1), 3)}
    clean = [r for r in rows if r["fault"] == "none"]
    summary = {
        "n_scans": len(rows),
        "videos": videos(),
        "clean_bursts": len(clean),
        "clean_alarm_rate": round(float(np.mean([bool(r["fired"]) for r in clean])), 3),
        "baseline_clean_alarm_rate": round(float(np.mean([r["baseline"] for r in clean])), 3),
        "recall_sev3plus": round(float(np.mean([any(e in r["fired"] for e in ALTERNATIVES.get(r["fault"], (EXPECTED_CHECK[r["fault"]],)))
                                                 for r in rows if r["severity"] >= 3])), 3),
        "baseline_recall_sev3plus": round(float(np.mean([r["baseline"] for r in rows if r["severity"] >= 3])), 3),
        "faults": table,
    }
    save("e1/detection.json", summary)
    save("e1/rows.json", rows)


if __name__ == "__main__":
    main()

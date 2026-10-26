"""Figures for REPORT.md from results/*.json → results/figs/*.png (OpenCV drawing, no matplotlib)."""

from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np

R = Path(__file__).resolve().parents[1] / "results"
OUT = R / "figs"
W, H, PAD = 900, 600, 70


def canvas(title: str) -> np.ndarray:
    img = np.full((H, W, 3), 255, np.uint8)
    cv2.putText(img, title, (PAD, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (30, 30, 30), 2, cv2.LINE_AA)
    cv2.line(img, (PAD, H - PAD), (W - 30, H - PAD), (0, 0, 0), 1)
    cv2.line(img, (PAD, H - PAD), (PAD, 60), (0, 0, 0), 1)
    return img


def xy(x: float, y: float, xmax: float = 1, ymax: float = 1) -> tuple[int, int]:
    return int(PAD + x / xmax * (W - PAD - 30)), int(H - PAD - y / ymax * (H - PAD - 60))


def scatter(pred: list[float], true: list[float], title: str, xl: str, yl: str, name: str) -> None:
    img = canvas(title)
    m = max(max(pred + true, default=1), 1e-6)
    cv2.line(img, xy(0, 0, m, m), xy(m, m, m, m), (180, 180, 180), 1, cv2.LINE_AA)
    for p, t in zip(pred, true, strict=True):
        cv2.circle(img, xy(t, p, m, m), 3, (200, 90, 30), -1, cv2.LINE_AA)
    cv2.putText(img, xl, (W // 2 - 80, H - 25), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 0), 1, cv2.LINE_AA)
    cv2.putText(img, yl, (10, 55), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 0), 1, cv2.LINE_AA)
    for v in (0, m / 2, m):
        cv2.putText(img, f"{v:.2f}", (xy(v, 0, m, m)[0] - 15, H - PAD + 20), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 1)
        cv2.putText(img, f"{v:.2f}", (20, xy(0, v, m, m)[1] + 5), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 1)
    cv2.imwrite(str(OUT / name), img)


def recall_curves(e1: dict) -> None:  # type: ignore[type-arg]
    img = canvas("E1: recall vs severity (sev>=2 alarm)")
    rng = np.random.default_rng(3)
    for i, (f, d) in enumerate(e1["faults"].items()):
        col = tuple(int(c) for c in rng.integers(30, 220, 3))
        pts = [xy(s - 1, d["per_severity"][str(s)]["recall"], 4, 1) for s in range(1, 6)]
        cv2.polylines(img, [np.array(pts)], False, col, 2, cv2.LINE_AA)
        cv2.putText(img, f, (W - 170, 70 + 22 * i), cv2.FONT_HERSHEY_SIMPLEX, 0.5, col, 1, cv2.LINE_AA)
    for s in range(1, 6):
        cv2.putText(img, str(s), (xy(s - 1, 0, 4, 1)[0] - 4, H - PAD + 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
    cv2.imwrite(str(OUT / "e1_recall.png"), img)


def bars(labels: list[str], vals: list[float], title: str, name: str, vmax: float | None = None) -> None:
    img = canvas(title)
    vmax = vmax or max(vals + [1e-6])
    bw = (W - PAD - 40) // max(len(vals), 1)
    for i, (lab, v) in enumerate(zip(labels, vals, strict=True)):
        x0 = PAD + 10 + i * bw
        y = xy(0, v, 1, vmax)[1]
        cv2.rectangle(img, (x0, y), (x0 + bw - 10, H - PAD), (200, 120, 40), -1)
        cv2.putText(img, f"{v:.2f}", (x0, y - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 1)
        cv2.putText(img, lab[:12], (x0, H - PAD + 18), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 0), 1)
    cv2.imwrite(str(OUT / name), img)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    if (R / "e3/scatter.json").exists():
        s = json.loads((R / "e3/scatter.json").read_text())
        scatter(s["agreement"]["pred"], s["agreement"]["true"], "E3a: predicted vs actual agreement (held-out video)",
                "actual agreement", "predicted", "e3_agreement.png")
        if s["ap"]["pred_drop"]:
            scatter(s["ap"]["pred_drop"], s["ap"]["true_drop"], "E3b: predicted drop vs TRUE MOT17 AP drop",
                    "true relative AP drop", "predicted drop", "e3_true_ap.png")
    if (R / "e1/detection.json").exists():
        recall_curves(json.loads((R / "e1/detection.json").read_text()))
    if (R / "e4/repair.json").exists():
        e4 = json.loads((R / "e4/repair.json").read_text())
        labs = [f for f in e4 if e4[f]["accuracy_recovered_mean"] is not None]
        bars(labs, [e4[f]["accuracy_recovered_mean"] for f in labs], "E4: accuracy recovered by verified repair",
             "e4_recovered.png", 1.0)
    print("figures in", OUT)


if __name__ == "__main__":
    main()

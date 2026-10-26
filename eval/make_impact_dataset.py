"""Build the impact-predictor dataset (docs/03 §6.5, docs/06 §3 E3).

For every (video, burst, fault, severity) — plus sampled two-fault combinations — inject the
fault into a 3-frame burst, scan it, run the detector on degraded and clean frames and record:
features (label-free), target = mean agreement F1 vs. clean detections, and for MOT17 also
person AP@0.5 against real labels on the clean and degraded burst.

Output: results/impact/dataset.csv (+ .npz with the feature matrix).
"""

from __future__ import annotations

import argparse
import csv
import itertools
import os
import random
import time
from multiprocessing import get_context
from pathlib import Path

import numpy as np

os.environ.setdefault("OMP_NUM_THREADS", "4")

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "impact"
SEED = 7
REF_FRAMES = list(range(0, 240, 4))
BURST_STEP = 3
TRAIN_FAULTS = [
    "drift", "vibration", "haze", "condensation", "glare", "exposure", "color_cast",
    "ir_cut_stuck", "noise", "occlusion", "smudge", "defocus", "freeze", "dead",
]


def _prep_video(name: str, n_bursts: int) -> tuple[str, list[int]]:
    import cv2

    from visiondoctor.health.reference import learn_reference
    from visiondoctor.impact.predictor import detector_baseline
    from visiondoctor.sim import sources

    n = sources.frame_count(name)
    starts = np.linspace(250, n - 3 * BURST_STEP - 1, n_bursts).astype(int).tolist()
    idx = set(REF_FRAMES)
    for s in starts:
        idx.update(s + k * BURST_STEP for k in range(3))
    frames = sources.read_frames(name, sorted(idx))
    ref = learn_reference(name, [frames[i] for i in REF_FRAMES])
    ref.detector_baseline = detector_baseline([frames[i] for i in REF_FRAMES[::6]])
    cache = OUT / "cache" / name
    ref.save(cache / "reference")
    for i, f in frames.items():
        if i not in REF_FRAMES:
            cv2.imwrite(str(cache / f"{i}.png"), f)
    return name, starts


def _task(args: tuple[str, int, list[tuple[str, int]]]) -> list[dict[str, object]]:
    import cv2

    cv2.setNumThreads(4)
    from visiondoctor.health.checks.base import CameraState
    from visiondoctor.health.reference import Reference
    from visiondoctor.health.scan import scan
    from visiondoctor.impact.agreement import agreement, average_precision
    from visiondoctor.impact.detector import get_detector
    from visiondoctor.impact.features import FEATURE_NAMES, detector_signals, feature_vector
    from visiondoctor.sim import sources
    from visiondoctor.sim.faults import Fault

    name, start, combos = args
    cache = OUT / "cache" / name
    ref = Reference.load(cache / "reference")
    idx = [start + k * BURST_STEP for k in range(3)]
    clean = [cv2.imread(str(cache / f"{i}.png")) for i in idx]
    det = get_detector()
    clean_d = [det.detect(f) for f in clean]
    gt = sources.mot17_gt(name)
    rows = []
    for combo in [(("none", 0),)] + [tuple(c) for c in combos]:
        faults = [Fault(f, s, seed=SEED + start) for f, s in combo if f != "none"]
        frames = []
        for f in clean:
            for flt in faults:
                f = flt.apply(f)
            frames.append(f)
        rep = scan(name, frames, ref, CameraState())
        deg_d = [det.detect(f) for f in frames]
        y = float(np.mean([agreement(d, c) for d, c in zip(deg_d, clean_d, strict=True)]))
        x = feature_vector(rep, detector_signals(deg_d, ref.detector_baseline))
        row: dict[str, object] = {
            "video": name,
            "start": start,
            "faults": "+".join(f for f, _ in combo),
            "severity": max(s for _, s in combo),
            "agreement": y,
        }
        if gt is not None:
            g = [gt.get(i, np.zeros((0, 4))) for i in idx]

            def persons(ds):  # noqa: ANN001, ANN202
                return [(d.boxes[d.classes == 0], d.scores[d.classes == 0]) for d in ds]

            row["ap_clean"] = average_precision(persons(clean_d), g)
            row["ap_degraded"] = average_precision(persons(deg_d), g)
        row.update(dict(zip(FEATURE_NAMES, x.tolist(), strict=True)))
        rows.append(row)
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bursts", type=int, default=10)
    ap.add_argument("--combos", type=int, default=12, help="two-fault combinations per burst")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--videos", nargs="*")
    args = ap.parse_args()
    from visiondoctor.sim import sources

    rng = random.Random(SEED)
    vids = args.videos or sources.available()
    OUT.mkdir(parents=True, exist_ok=True)
    tasks = []
    singles = [((f, s),) for f in TRAIN_FAULTS for s in range(1, 6)]
    pairable = [f for f in TRAIN_FAULTS if f not in ("dead", "freeze")]
    for name in vids:
        (OUT / "cache" / name).mkdir(parents=True, exist_ok=True)
        _, starts = _prep_video(name, args.bursts)
        for s in starts:
            pairs = [
                ((a, rng.randint(1, 5)), (b, rng.randint(1, 5)))
                for a, b in rng.sample(list(itertools.combinations(pairable, 2)), args.combos)
            ]
            tasks.append((name, s, singles + pairs))
    t0 = time.time()
    rows: list[dict[str, object]] = []
    # spawn, not fork: the parent already ran OpenCV (thread pools do not survive fork).
    with get_context("spawn").Pool(args.workers) as pool:
        for i, r in enumerate(pool.imap_unordered(_task, tasks), 1):
            rows.extend(r)
            print(f"{i}/{len(tasks)} tasks, {len(rows)} rows, {time.time() - t0:.0f}s", flush=True)
    keys = sorted({k for r in rows for k in r}, key=lambda k: (k not in ("video", "start", "faults"), k))
    with open(OUT / "dataset.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)
    print("wrote", OUT / "dataset.csv", len(rows))


if __name__ == "__main__":
    main()
